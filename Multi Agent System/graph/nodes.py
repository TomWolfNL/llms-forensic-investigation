# =========================
# CORE PIPELINE NODES
# =========================

from agents.timeline_agent import TimelineAgent
from agents.attribute_agent import AttributeAgent
from agents.behavioral_agent import BehavioralConsistencyAgent
from agents.contradiction_agent import TimelineContradictionAgent
from agents.credibility_agent import CredibilityOfInformationAgent
from agents.reliability_agent  import ReliabilityOfSourceAgent
from agents.extraction_agent import StatementExtractionAgent

import json
import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("pipeline")

# All intermediate and final result files land here
_DEBUG_DIR = Path(__file__).parent.parent / "results"
_DEBUG_DIR.mkdir(exist_ok=True)


def _save_debug(filename: str, data) -> None:
    """Write intermediate pipeline output to a JSON file for inspection."""
    path = _DEBUG_DIR / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_deep_normalize(data), f, indent=2, ensure_ascii=False)
        log.info(f"[debug] Saved: {path.name}")
    except Exception as e:
        log.warning(f"[debug] Could not save {filename}: {e}")


# =========================
# NORMALIZATION HELPERS
# =========================

def _deep_normalize(obj):
    """
    Converts ANY structure into pure JSON-safe primitives.
    Prevents LangChain / Pydantic leakage into agent calls.
    """
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, dict):
        return {str(k): _deep_normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_deep_normalize(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


# =========================
# PIPELINE NODES
# =========================

async def extraction_node(state):
    from agents.extraction_agent import BATCH_SIZE
    witnesses = state.raw_story.get("witnesses", [])
    n_batches = -(-len(witnesses) // BATCH_SIZE)
    log.info(f"[extraction] Starting — {len(witnesses)} witnesses in {n_batches} batches of {BATCH_SIZE}")
    
    # 1. Unpack Result and Telemetry
    result, telemetry = await StatementExtractionAgent().run(state.raw_story)
    
    log.info(f"[extraction] Done — {len(result)} statements extracted total")
    _save_debug("extracted_statements.json", result)
    
    # 2. Append to Graph State
    telemetry_list = telemetry if isinstance(telemetry, list) else [telemetry]
    return {"statements": result, "telemetry_log": telemetry_list}


async def timeline_node(state):
    log.info(f"[timeline] Starting — {len(state.statements)} statements")
    
    result, telemetry = await TimelineAgent().run(state.statements)
    
    log.info(f"[timeline] Done — {len(result)} events built")
    _save_debug("timeline.json", result)
    
    telemetry_list = telemetry if isinstance(telemetry, list) else [telemetry]
    return {"timeline": result, "telemetry_log": telemetry_list}


async def attribute_node(state):
    from agents.attribute_agent import ATTRIBUTE_BATCH_SIZE
    n_batches = -(-len(state.statements) // ATTRIBUTE_BATCH_SIZE)
    log.info(f"[attribute] Starting — {len(state.statements)} statements in {n_batches} batches of {ATTRIBUTE_BATCH_SIZE}")
    
    result, telemetry = await AttributeAgent().run(state.statements)
    
    log.info(f"[attribute] Done — {len(result)} person attribute records")
    _save_debug("extracted_attributes.json", result)
    
    telemetry_list = telemetry if isinstance(telemetry, list) else [telemetry]
    return {"attributes": result, "telemetry_log": telemetry_list}


async def contradiction_node(state):
    log.info(f"[contradiction] Starting — {len(state.timeline)} events")
    
    result, telemetry = await TimelineContradictionAgent().run(state.timeline)
    
    log.info(f"[contradiction] Done — {len(result)} contradictions found")
    _save_debug("contradictions.json", result)
    
    telemetry_list = telemetry if isinstance(telemetry, list) else [telemetry]
    return {"contradictions": result, "telemetry_log": telemetry_list}


MAX_BEHAVIORAL_ISSUES = 20

async def behavioral_node(state):
    log.info(f"[behavior] Starting — {len(state.statements)} statements, {len(state.attributes)} attribute records")
    
    result, telemetry = await BehavioralConsistencyAgent().run(
        state.statements,
        state.attributes
    )
    
    if len(result) > MAX_BEHAVIORAL_ISSUES:
        log.warning(f"[behavior] Capping {len(result)} issues to {MAX_BEHAVIORAL_ISSUES}")
        result = result[:MAX_BEHAVIORAL_ISSUES]
        
    log.info(f"[behavior] Done — {len(result)} behavioral issues identified")
    _save_debug("behavior_report.json", result)
    
    telemetry_list = telemetry if isinstance(telemetry, list) else [telemetry]
    return {"behavior_report": result, "telemetry_log": telemetry_list}

# =========================
# DEBUG INSPECTOR NODE
# =========================

def _safe_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def debug_inspector_node(state):
    """
    Lightweight deterministic inspector.
    Runs BEFORE credibility and reliability nodes.
    """
    log.info("[debug_inspector] Starting — building per-witness data maps")

    trace = []
    statements = _safe_get(state, "statements", [])
    contradictions = _safe_get(state, "contradictions", [])
    behavior_report = _safe_get(state, "behavior_report", [])
    timeline = _safe_get(state, "timeline", [])

    event_to_witnesses = {}
    for e in timeline:
        eid = e["event_id"] if isinstance(e, dict) else e.event_id
        w = e["witnesses"] if isinstance(e, dict) else e.witnesses
        event_to_witnesses[eid] = w

    witnesses = {
        s["witness"] if isinstance(s, dict) else s.witness
        for s in statements
    }

    for witness in witnesses:
        witness_statements = [
            _deep_normalize(s) for s in statements
            if (s.get("witness") if isinstance(s, dict) else s.witness) == witness
        ]

        witness_statement_ids = [
            s["statement_id"] if isinstance(s, dict) else s.statement_id
            for s in witness_statements
        ]

        witness_contradictions = []
        for c in contradictions:
            event_ids = c["event_ids"] if isinstance(c, dict) else c.event_ids
            involved = set()
            for eid in event_ids:
                involved.update(event_to_witnesses.get(eid, []))

            if witness in involved:
                witness_contradictions.append(
                    c["contradiction_id"] if isinstance(c, dict) else c.contradiction_id
                )

        witness_behavior = [
            b for b in behavior_report
            if (b["person"] if isinstance(b, dict) else b.person) == witness
        ]

        trace.append({
            "witness": witness,
            "stats": {
                "statement_count": len(witness_statements),
                "statement_ids": witness_statement_ids,
                "contradiction_count": len(witness_contradictions),
                "behavior_count": len(witness_behavior),
            },
            "data_health": {
                "has_statements": len(witness_statements) > 0,
                "has_contradictions": len(witness_contradictions) > 0,
                "has_behavior": len(witness_behavior) > 0
            }
        })

    log.info(f"[debug_inspector] Done — {len(trace)} witnesses mapped")
    
    # -------------------------------------------------------------
    # THE FIX: Only return the newly generated debug_trace!
    # Do NOT return the full 'state' object.
    # -------------------------------------------------------------
    return {"debug_trace": trace}


# =========================
# SHARED WITNESS PAYLOAD BUILDER
# =========================

def _build_witness_payloads(state):
    """
    Builds a per-witness payload dict used by both
    credibility_node and reliability_node.
    """
    statements = getattr(state, "statements", []) or []
    contradictions = getattr(state, "contradictions", []) or []
    behavior_report = getattr(state, "behavior_report", []) or []
    timeline = getattr(state, "timeline", []) or []

    witnesses = []
    for s in statements:
        witness = s.get("witness") if isinstance(s, dict) else getattr(s, "witness", None)
        if witness:
            witnesses.append(str(witness).strip())
    witnesses = sorted(set(witnesses))

    event_to_witnesses = {}
    for e in timeline:
        normalized = _deep_normalize(e)
        event_id = normalized.get("event_id")
        event_to_witnesses[event_id] = [str(w).strip() for w in normalized.get("witnesses", [])]

    payloads = []
    for witness in witnesses:
        witness_key = str(witness).strip().lower()
        witness_statements = []

        for s in statements:
            normalized = _deep_normalize(s)
            sw = str(normalized.get("witness", "")).strip().lower()
            if sw == witness_key:
                witness_statements.append(normalized)

        statement_ids = {str(s["statement_id"]).strip() for s in witness_statements if s.get("statement_id")}
        witness_contradictions = []
        seen_pairs = set()

        for c in contradictions:
            normalized = _deep_normalize(c)
            event_ids = tuple(sorted(normalized.get("event_ids", [])))
            if not event_ids or event_ids in seen_pairs:
                continue

            involved = set()
            for eid in event_ids:
                involved.update(event_to_witnesses.get(eid, []))
            
            involved = {x.lower().strip() for x in involved}

            if witness_key in involved:
                witness_contradictions.append(normalized)
                seen_pairs.add(event_ids)

        witness_behavior = []
        for b in behavior_report:
            normalized = _deep_normalize(b)
            explanation = normalized.get("explanation", "").lower()
            attach = False

            if any(sid.lower() in explanation for sid in statement_ids):
                attach = True
            elif witness_key in explanation:
                attach = True

            if attach:
                witness_behavior.append(normalized)

        payload = _deep_normalize({
            "witness": witness,
            "statements": witness_statements,
            "contradictions": witness_contradictions,
            "behavior": witness_behavior
        })
        payloads.append((witness, witness_key, payload))

    return payloads


# =========================
# CREDIBILITY OF INFORMATION NODE
# =========================

async def credibility_node(state):
    payloads = _build_witness_payloads(state)
    log.info(f"[credibility] Starting — {len(payloads)} witnesses to grade (1-6 scale)")

    results = []
    node_telemetry = [] # Array to hold metrics for this node's loop

    for i, (witness, witness_key, payload) in enumerate(payloads, 1):
        log.info(f"[credibility] ({i}/{len(payloads)}) Grading: {witness}")

        try:
            # 1. Unpack Result and Telemetry
            result, telemetry = await CredibilityOfInformationAgent().run(payload)
            
            # Append local metrics to node array
            if isinstance(telemetry, list):
                node_telemetry.extend(telemetry)
            else:
                node_telemetry.append(telemetry)

            returned = str(result.witness).strip()
            if not returned: raise ValueError("Missing witness")
            if returned.lower() != witness_key: raise ValueError(f"Witness mismatch {returned}")
            if not result.evidence: raise ValueError("Evidence missing")

            if result.metrics is None:
                metrics_dict = None
                grade = 6
                weighted_score = 0.0
                log.info(f"[credibility] ({i}/{len(payloads)}) {witness} → NO STATEMENTS → grade 6")
            else:
                metrics_dict = result.metrics.model_dump()
                ic = float(metrics_dict.get("internal_consistency", 0.0))
                pi = float(metrics_dict.get("physical_impossibility", 0.0))
                om = float(metrics_dict.get("orchestration_marker", 0.0))
                dq = float(metrics_dict.get("detail_quality", 0.0))

                weighted_score = (0.25 * ic) + (0.25 * pi) + (0.25 * om) + (0.25 * dq)

                if weighted_score >= 0.80: grade = 1
                elif weighted_score >= 0.65: grade = 2
                elif weighted_score >= 0.50: grade = 3
                elif weighted_score >= 0.35: grade = 4
                elif weighted_score >= 0.15: grade = 5
                else: grade = 6

                log.info(f"[credibility] ({i}/{len(payloads)}) {witness} → score: {weighted_score:.3f} → grade {grade}")

            results.append({
                "witness": returned,
                "evidence": [e.model_dump() for e in result.evidence],
                "metrics": metrics_dict,
                "credibility_grade": grade,
                "weighted_score": round(weighted_score, 3)
            })

        except Exception as e:
            log.warning(f"[credibility] ({i}/{len(payloads)}) {witness} → FAILED: {e}")
            results.append({
                "witness": witness,
                "evidence": [],
                "metrics": None,
                "credibility_grade": 6,
                "error": str(e)
            })

    log.info(f"[credibility] Done — {len(results)} witnesses graded")
    _save_debug("credibility_metrics.json", results)
    
    # Return both results and aggregated array of metrics to state
    return {
        "credibility_metrics": results,
        "telemetry_log": node_telemetry
    }

# =========================
# RELIABILITY OF SOURCE NODE
# =========================

async def reliability_node(state):
    payloads = _build_witness_payloads(state)
    log.info(f"[reliability] Starting — {len(payloads)} witnesses to grade (A-F scale)")

    results = []
    node_telemetry = []

    for i, (witness, witness_key, payload) in enumerate(payloads, 1):
        log.info(f"[reliability] ({i}/{len(payloads)}) Grading: {witness}")

        try:
            # 1. Unpack Result and Telemetry
            result, telemetry = await ReliabilityOfSourceAgent().run(payload)
            
            # Append local metrics to node array
            if isinstance(telemetry, list):
                node_telemetry.extend(telemetry)
            else:
                node_telemetry.append(telemetry)

            returned = str(result.witness).strip()
            if not returned: raise ValueError("Missing witness")
            if returned.lower() != witness_key: raise ValueError(f"Witness mismatch {returned}")
            if result.grade not in ("A", "B", "C", "D", "E", "F"): raise ValueError(f"Invalid reliability grade: {result.grade}")
            if not result.explanation: raise ValueError("Missing explanation")
            if not result.factors_assessed: raise ValueError("Missing factors_assessed")

            log.info(f"[reliability] ({i}/{len(payloads)}) {witness} → grade {result.grade}")

            results.append({
                "witness": returned,
                "grade": result.grade,
                "explanation": result.explanation,
                "factors_assessed": result.factors_assessed
            })

        except Exception as e:
            log.warning(f"[reliability] ({i}/{len(payloads)}) {witness} → FAILED: {e}")
            results.append({
                "witness": witness,
                "grade": "F",
                "explanation": "Reliability of source evaluation failed.",
                "factors_assessed": [str(e)]
            })

    log.info(f"[reliability] Done — {len(results)} witnesses graded")
    _save_debug("reliability_grades.json", results)
    
    # Return both results and aggregated array of metrics to state
    return {
        "reliability_grades": results,
        "telemetry_log": node_telemetry
    }


# =========================
# REPORT NODE
# =========================

async def report_node(state):
    log.info("[report] Assembling final report")

    report = {
        "timeline": _deep_normalize(getattr(state, "timeline", [])),
        "contradictions": _deep_normalize(getattr(state, "contradictions", [])),
        "attributes": _deep_normalize(getattr(state, "attributes", [])),
        "behavior_report": _deep_normalize(getattr(state, "behavior_report", [])),
        "credibility_metrics": _deep_normalize(getattr(state, "credibility_metrics", [])),
        "reliability_grades": _deep_normalize(getattr(state, "reliability_grades", [])),
        "debug_trace": _deep_normalize(getattr(state, "debug_trace", [])),
        # Attach the accumulated telemetry array to final report here
        "telemetry_log": _deep_normalize(getattr(state, "telemetry_log", []))
    }

    log.info("[report] Done — final report ready")

    return {
        "final_report": report
    }