import asyncio
import json
import logging
import re
import time
import sys
from typing import Type, Any

from pydantic import BaseModel

from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from utils.llm import create_llm

# Timeout and retry applied to every raw LLM call
_LLM_CALL_TIMEOUT = 200
_LLM_CALL_RETRIES = 3

try:
    from json_repair import repair_json as _repair_json
    _JSON_REPAIR_AVAILABLE = True
except ImportError:
    _JSON_REPAIR_AVAILABLE = False

log = logging.getLogger("pipeline")

def to_clean_json(obj):
    """
    HARD SERIALIZATION LAYER
    Converts ANY object into strict JSON-safe dict/list structure.
    """

    if hasattr(obj, "model_dump"):
        return to_clean_json(obj.model_dump())

    if isinstance(obj, dict):
        return {k: to_clean_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_clean_json(x) for x in obj]

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    return str(obj)

def extract_json(raw: str) -> dict:

    if not isinstance(raw, str):
        return raw

    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = re.sub(r"```json", "", raw)
    raw = re.sub(r"```", "", raw)

    start = raw.find("{")
    if start == -1:
        raise ValueError(f"No JSON found:\n{raw}")

    brace_count = 0
    end = None

    for i in range(start, len(raw)):
        if raw[i] == "{":
            brace_count += 1
        elif raw[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    # If unclosed, take everything from start to end of string and attempt repair
    json_str = raw[start:end].strip() if end is not None else raw[start:].strip()

    # First attempt: strict parse
    try:
        return json.loads(json_str)

    except json.JSONDecodeError as first_err:

        # Second attempt: json-repair library
        if _JSON_REPAIR_AVAILABLE:
            try:
                repaired = _repair_json(json_str, return_objects=True)
                if isinstance(repaired, dict):
                    log.warning(f"[json-repair] Fixed malformed JSON ({first_err})")
                    return repaired
            except Exception:
                pass

        raise ValueError(
            f"JSON parse error: {first_err}\n\n{json_str[:500]}"
        )


def _is_credibility_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the CredibilityResult (has metrics + credibility_grade)."""
    fields = schema.model_fields
    return "credibility_grade" in fields and "metrics" in fields


def _is_reliability_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the ReliabilityResult (has grade + factors_assessed)."""
    fields = schema.model_fields
    return "grade" in fields and "factors_assessed" in fields


def _is_extraction_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the ExtractionResult (has statements list)."""
    fields = schema.model_fields
    return "statements" in fields and len(fields) == 1


def _is_attribute_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the AttributeResult (has people list)."""
    fields = schema.model_fields
    return "people" in fields and len(fields) == 1


def _is_contradiction_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the ContradictionResult (has contradictions + analysis_scratchpad)."""
    fields = schema.model_fields
    return "contradictions" in fields and "analysis_scratchpad" in fields


def _is_baseline_schema(schema: Type[BaseModel]) -> bool:
    """Returns True if schema is the BaselineResult (has evaluations + final_case_summary)."""
    fields = schema.model_fields
    return "evaluations" in fields and "final_case_summary" in fields


def schema_repair(data: dict, schema: Type[BaseModel]) -> dict:
    """
    Repairs common LLM schema failures BEFORE Pydantic validation.
    Schema-aware branches: CredibilityResult, ReliabilityResult, AttributeResult,
    ExtractionResult, ContradictionResult, BehaviorResult.
    Unknown schemas are passed through unchanged (no destructive defaults).
    """

    if not isinstance(data, dict):
        return {}

    repaired = dict(data)

    # ------------------------------------------------------------------
    # CREDIBILITY OF INFORMATION MODEL
    # Has: witness, evidence, metrics (5 floats), credibility_grade (int)
    # ------------------------------------------------------------------
    if _is_credibility_schema(schema):

        # The 4 new Anomaly Hunter metrics
        _credibility_metric_defaults = {
            "internal_consistency": 0.5,
            "physical_impossibility": 0.5,
            "orchestration_marker": 0.5,
            "detail_quality": 0.5,
        }
        repaired.setdefault("witness", "Unknown Witness")
        repaired.setdefault("evidence", [])

        repaired.setdefault("metrics", _credibility_metric_defaults.copy())

        repaired.setdefault("credibility_grade", 6)

        # metrics safety
        if isinstance(repaired.get("metrics"), dict):
            for mk, default in _credibility_metric_defaults.items():
                repaired["metrics"].setdefault(mk, default)
                try:
                    repaired["metrics"][mk] = float(repaired["metrics"][mk])
                except Exception:
                    repaired["metrics"][mk] = default

        # evidence list safety
        if not isinstance(repaired.get("evidence"), list):
            repaired["evidence"] = []

        # credibility_grade: coerce to int, clamp to 1-6
        try:
            grade = int(float(repaired.get("credibility_grade", 6)))
            repaired["credibility_grade"] = max(1, min(6, grade))
        except Exception:
            repaired["credibility_grade"] = 6

        # remove obsolete total_score if LLM still outputs it
        repaired.pop("total_score", None)

    # ------------------------------------------------------------------
    # RELIABILITY OF SOURCE MODEL
    # Has: witness, grade (A-F), explanation, factors_assessed (list)
    # ------------------------------------------------------------------
    elif _is_reliability_schema(schema):

        repaired.setdefault("grade", "F")
        repaired.setdefault("explanation", "")
        repaired.setdefault("factors_assessed", [])

        # grade safety: must be A-F
        if repaired.get("grade") not in ("A", "B", "C", "D", "E", "F"):
            repaired["grade"] = "F"

        # factors_assessed safety
        if not isinstance(repaired.get("factors_assessed"), list):
            repaired["factors_assessed"] = []

    # ------------------------------------------------------------------
    # ATTRIBUTE MODEL
    # Has: people (list of PersonAttributes)
    # ------------------------------------------------------------------
    elif _is_attribute_schema(schema):

        if not isinstance(repaired.get("people"), list):
            repaired["people"] = []

        cleaned = []
        for p in repaired.get("people", []):
            if not isinstance(p, dict):
                continue
            if not p.get("person"):
                continue
            if not isinstance(p.get("attributes"), list):
                p["attributes"] = []
            cleaned.append(p)

        repaired["people"] = cleaned

    # ------------------------------------------------------------------
    # EXTRACTION MODEL
    # Has: statements (list of ExtractedStatement)
    # ------------------------------------------------------------------
    elif _is_extraction_schema(schema):

        # ensure statements key exists and is a list
        if not isinstance(repaired.get("statements"), list):
            repaired["statements"] = []

        # ensure each statement has minimum required fields
        cleaned = []
        for s in repaired["statements"]:
            if not isinstance(s, dict):
                continue
            if not s.get("statement_id") or not s.get("witness") or not s.get("raw_text"):
                continue
            s.setdefault("subject", None)
            s.setdefault("time", None)
            s.setdefault("location", None)
            s.setdefault("action", None)
            s.setdefault("context", None)
            cleaned.append(s)

        repaired["statements"] = cleaned

    # ------------------------------------------------------------------
    # CONTRADICTION MODEL
    # Has: analysis_scratchpad (str), contradictions (list)
    # ------------------------------------------------------------------
    elif _is_contradiction_schema(schema):

        repaired.setdefault("analysis_scratchpad", "")
        repaired.setdefault("contradictions", [])

        if not isinstance(repaired.get("contradictions"), list):
            repaired["contradictions"] = []

        if not isinstance(repaired.get("analysis_scratchpad"), str):
            repaired["analysis_scratchpad"] = ""

    # ------------------------------------------------------------------
    # BEHAVIOR MODEL
    # Has: analysis_scratchpad (str), issues (list of BehavioralIssue)
    # ------------------------------------------------------------------
    elif (
        "issues" in schema.model_fields
        and "analysis_scratchpad" in schema.model_fields
    ):
        repaired.setdefault("analysis_scratchpad", "Fallback: Failed to parse reasoning.")
        repaired.setdefault("issues", [])

        if not isinstance(repaired.get("issues"), list):
            repaired["issues"] = []

        if not isinstance(repaired.get("analysis_scratchpad"), str):
            repaired["analysis_scratchpad"] = "Fallback: Failed to parse reasoning."

    # ------------------------------------------------------------------
    # BASELINE MODEL
    # Has: evaluations (list of WitnessEvaluation), final_case_summary (str)
    # ------------------------------------------------------------------
    elif _is_baseline_schema(schema):

        repaired.setdefault("evaluations", [])
        repaired.setdefault("final_case_summary", "")

        if not isinstance(repaired.get("evaluations"), list):
            repaired["evaluations"] = []

        if not isinstance(repaired.get("final_case_summary"), str):
            repaired["final_case_summary"] = str(repaired.get("final_case_summary", ""))

        cleaned = []
        for ev in repaired["evaluations"]:
            if not isinstance(ev, dict):
                continue
            ev.setdefault("witness", "Unknown")
            ev.setdefault("reliability_grade", "F")
            ev.setdefault("credibility_grade", 6)
            ev.setdefault("reasoning", "")
            ev.setdefault("prime_suspect_likelihood", 0.0)
            if ev.get("reliability_grade") not in ("A", "B", "C", "D", "E", "F"):
                ev["reliability_grade"] = "F"
            try:
                ev["credibility_grade"] = max(1, min(6, int(float(ev["credibility_grade"]))))
            except Exception:
                ev["credibility_grade"] = 6
            try:
                ev["prime_suspect_likelihood"] = max(0.0, min(1.0, float(ev["prime_suspect_likelihood"])))
            except Exception:
                ev["prime_suspect_likelihood"] = 0.0
            cleaned.append(ev)

        repaired["evaluations"] = cleaned

    # ------------------------------------------------------------------
    # GENERIC FALLBACK — pass data through unchanged so valid LLM output
    # for unrecognised schemas is never overwritten with wrong defaults.
    # ------------------------------------------------------------------
    # (no-op: repaired already holds a copy of the incoming data)

    return repaired


# =========================================================
# STRUCTURED AGENT
# =========================================================

class StructuredAgent:

    def __init__(
        self,
        prompt: str,
        output_schema: Type[BaseModel]
    ):
        self.prompt = prompt
        self.output_schema = output_schema
        self.llm = create_llm()

    # Added agent_name parameter for cleaner telemetry dashboards
    async def invoke(self, payload, agent_name: str = None) -> tuple:
        
        # -----------------------------
        # 0. TELEMETRY INIT
        # -----------------------------
        start_time = time.perf_counter()
        payload_size = sys.getsizeof(str(payload))
        
        total_calls = 0
        successful_calls = 0
        input_tokens = 0
        output_tokens = 0
        
        # Default to the schema name if no specific agent name is provided
        if not agent_name:
            agent_name = self.output_schema.__name__

        # -----------------------------
        # 1. INPUT HANDLING
        # -----------------------------
        if isinstance(payload, dict) and "witness" in payload:
            system_prompt = f"""
{self.prompt}

-----------------------------
TARGET WITNESS (HARD BOUND)
-----------------------------
You MUST evaluate ONLY:
Witness = {payload["witness"]}
"""
            human_payload = to_clean_json(payload)
        else:
            system_prompt = self.prompt
            human_payload = {"input": to_clean_json(payload)}

        # -----------------------------
        # 2. MESSAGE BUILDING
        # -----------------------------
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=json.dumps(
                    human_payload,
                    indent=2,
                    ensure_ascii=False
                )
            )
        ]

        # -----------------------------
        # 3. LLM CALL & PARSING (With Retries)
        # -----------------------------
        parsed_result = None
        last_err: Exception = RuntimeError("No LLM attempts made")

        for attempt in range(1, _LLM_CALL_RETRIES + 1):
            total_calls += 1
            _t0 = time.monotonic()
            
            try:
                raw_response = await asyncio.wait_for(
                    self.llm.ainvoke(messages),
                    timeout=_LLM_CALL_TIMEOUT
                )
                _elapsed = time.monotonic() - _t0
                log.info(f"[llm] [{agent_name}] Response received in {_elapsed:.1f}s "
                         f"(attempt {attempt}/{_LLM_CALL_RETRIES})")

                # Track Tokens from the raw response
                if hasattr(raw_response, 'usage_metadata') and raw_response.usage_metadata:
                    input_tokens += raw_response.usage_metadata.get("input_tokens", 0)
                    output_tokens += raw_response.usage_metadata.get("output_tokens", 0)

                # Extract content
                raw_text = raw_response.content if hasattr(raw_response, "content") else raw_response

                # -----------------------------
                # 4. PARSING & VALIDATION 
                # -----------------------------
                # Moved inside the try-block so format failures trigger a retry
                data = extract_json(raw_text)
                data = schema_repair(data, self.output_schema)
                parsed_result = self.output_schema.model_validate(data)

                # If we make it here without an exception, it is a complete success!
                successful_calls += 1
                break

            except asyncio.TimeoutError:
                _elapsed = time.monotonic() - _t0
                last_err = asyncio.TimeoutError(
                    f"LLM timed out after {_elapsed:.0f}s"
                )
                log.warning(f"[llm] [{agent_name}] Attempt {attempt}/{_LLM_CALL_RETRIES} "
                            f"timed out after {_elapsed:.0f}s")

            except Exception as exc:
                _elapsed = time.monotonic() - _t0
                last_err = exc
                log.warning(f"[llm] [{agent_name}] Attempt {attempt}/{_LLM_CALL_RETRIES} "
                            f"failed formatting/validation: {exc}")

        # -----------------------------
        # 5. HARD FALLBACK 
        # -----------------------------
        if successful_calls == 0:
            log.error(f"[{agent_name}] All {total_calls} attempts failed. Applying empty fallback schema.")
            parsed_result = self.output_schema.model_validate(
                schema_repair({}, self.output_schema)
            )

        # -----------------------------
        # 6. TELEMETRY PACKAGING
        # -----------------------------
        end_time = time.perf_counter()
        
        telemetry_dict = {
            "agent_name": agent_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "execution_time_seconds": round(end_time - start_time, 2),
            "llm_success_ratio": f"{successful_calls}/{total_calls}",
            "payload_size_bytes": payload_size
        }

        # Returns the tuple required for Phase 4
        return parsed_result, telemetry_dict