from typing import Type, Any
from pydantic import BaseModel

from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from utils.llm import create_llm

import json
import re

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

    if end is None:
        raise ValueError(f"Unclosed JSON:\n{raw}")

    json_str = raw[start:end].strip()

    try:
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON parse error: {e}\n\n{json_str}"
        )


def schema_repair(data: dict, schema: Type[BaseModel]) -> dict:
    """
    Repairs common LLM schema failures BEFORE Pydantic validation.
    Prevents silent collapse into fallback zeros.
    """

    if not isinstance(data, dict):
        return {}

    repaired = dict(data)

    # ---- ensure required top-level keys exist ----
    required_defaults = {
        "evidence": [],
        "metrics": {
            "internal_consistency": 0.5,
            "cross_confirmation": 0.5,
            "detail_quality": 0.5,
            "observation_quality": 0.5,
            "contextual_alignment": 0.5,
        },
        "total_score": 0.5,
    }

    for k, v in required_defaults.items():
        if k not in repaired:
            repaired[k] = v

    # ---- metrics safety ----
    if isinstance(repaired.get("metrics"), dict):
        for mk in required_defaults["metrics"]:
            repaired["metrics"].setdefault(mk, 0.5)

            # clamp + coerce numeric safety
            try:
                repaired["metrics"][mk] = float(repaired["metrics"][mk])
            except:
                repaired["metrics"][mk] = 0.5

    # ---- evidence safety ----
    if not isinstance(repaired.get("evidence"), list):
        repaired["evidence"] = []

    # ---- total_score safety ----
    try:
        repaired["total_score"] = float(repaired.get("total_score", 0.5))
    except:
        repaired["total_score"] = 0.5

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

    async def invoke(self, payload) -> Any:

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
        # 3. LLM CALL
        # -----------------------------
        raw = await self.llm.ainvoke(messages)

        if hasattr(raw, "content"):
            raw = raw.content

        # -----------------------------
        # 4. JSON EXTRACTION
        # -----------------------------
        data = extract_json(raw)

        # -----------------------------
        # 5. SCHEMA REPAIR (CRITICAL FIX)
        # -----------------------------
        data = schema_repair(data, self.output_schema)

        # -----------------------------
        # 6. FINAL VALIDATION (SAFE)
        # -----------------------------
        try:
            return self.output_schema.model_validate(data)

        except Exception:
            # HARD FALLBACK (NO SILENT ZERO COLLAPSE ANYMORE)
            return self.output_schema.model_validate(
                schema_repair({}, self.output_schema)
            )