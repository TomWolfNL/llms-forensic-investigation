# =========================
# CORE PIPELINE NODES
# =========================

from agents.timeline_agent import TimelineAgent
from agents.attribute_agent import AttributeAgent
from agents.behavioral_agent import BehavioralConsistencyAgent
from agents.contradiction_agent import TimelineContradictionAgent

from agents.reliability_agent import CredibilityOfInformationAgent
from agents.credibility_agent import ReliabilityOfSourceAgent
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

    # Pydantic v2
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()

    # dict
    if isinstance(obj, dict):
        return {str(k): _deep_normalize(v) for k, v in obj.items()}

    # list / tuple / set
    if isinstance(obj, (list, tuple, set)):
        return [_deep_normalize(x) for x in obj]

    # primitives
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    # fallback (last resort safety)
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
    n_batches = -(-len(witnesses) // BATCH_SIZE)  # ceiling division
    log.info(f"[extraction] Starting — {len(witnesses)} witnesses in {n_batches} batches of {BATCH_SIZE}")
    result = await StatementExtractionAgent().run(state.raw_story)
    log.info(f"[extraction] Done — {len(result)} statements extracted total")
    _save_debug("extracted_statements.json", result)
    return {"statements": result}


async def timeline_node(state):
    log.info(f"[timeline] Starting — {len(state.statements)} statements")
    result = await TimelineAgent().run(state.statements)
    log.info(f"[timeline] Done — {len(result)} events built")
    _save_debug("timeline.json", result)
    return {"timeline": result}


async def attribute_node(state):
    from agents.attribute_agent import ATTRIBUTE_BATCH_SIZE
    n_batches = -(-len(state.statements) // ATTRIBUTE_BATCH_SIZE)
    log.info(f"[attribute] Starting — {len(state.statements)} statements in {n_batches} batches of {ATTRIBUTE_BATCH_SIZE}")
    result = await AttributeAgent().run(state.statements)
    log.info(f"[attribute] Done — {len(result)} person attribute records")
    _save_debug("extracted_attributes.json", result)
    return {"attributes": result}


async def contradiction_node(state):
    log.info(f"[contradiction] Starting — {len(state.timeline)} events")
    result = await TimelineContradictionAgent().run(state.timeline)
    log.info(f"[contradiction] Done — {len(result)} contradictions found")
    _save_debug("contradictions.json", result)
    return {"contradictions": result}


MAX_BEHAVIORAL_ISSUES = 10

async def behavioral_node(state):
    log.info(f"[behavior] Starting — {len(state.statements)} statements, {len(state.attributes)} attribute records")
    result = await BehavioralConsistencyAgent().run(
        state.statements,
        state.attributes
    )
    # Hard cap: never allow runaway issue generation
    if len(result) > MAX_BEHAVIORAL_ISSUES:
        log.warning(f"[behavior] Capping {len(result)} issues to {MAX_BEHAVIORAL_ISSUES}")
        result = result[:MAX_BEHAVIORAL_ISSUES]
    log.info(f"[behavior] Done — {len(result)} behavioral issues identified")
    _save_debug("behavior_report.json", result)
    return {"behavior_report": result}

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

    # -----------------------------
    # Build event → witnesses map
    # -----------------------------
    event_to_witnesses = {}

    for e in timeline:
        eid = e["event_id"] if isinstance(e, dict) else e.event_id
        w = e["witnesses"] if isinstance(e, dict) else e.witnesses
        event_to_witnesses[eid] = w

    # -----------------------------
    # Witness-level inspection
    # -----------------------------
    witnesses = {
        s["witness"] if isinstance(s, dict) else s.witness
        for s in statements
    }

    for witness in witnesses:

        witness_statements = [
            _deep_normalize(s)
            for s in statements
            if (
                s.get("witness")
                if isinstance(s, dict)
                else s.witness
            ) == witness
        ]

        witness_statement_ids = [
            s["statement_id"] if isinstance(s, dict) else s.statement_id
            for s in witness_statements
        ]

        # -----------------------------
        # contradiction scope check
        # -----------------------------
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

        # -----------------------------
        # behavior scope check
        # -----------------------------
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

    # -----------------------------
    # attach to state
    # -----------------------------
    if isinstance(state, dict):
        state["debug_trace"] = trace
    else:
        state.debug_trace = trace

    log.info(f"[debug_inspector] Done — {len(trace)} witnesses mapped")

    return state


# =========================
# SHARED WITNESS PAYLOAD BUILDER
# =========================

def _build_witness_payloads(state):
    """
    Builds a per-witness payload dict used by both
    credibility_node and reliability_node.
    Returns a list of normalized payload dicts.
    """

    statements = state.statements or []
    contradictions = state.contradictions or []
    behavior_report = state.behavior_report or []
    timeline = state.timeline or []

    # -------------------------------------------------
    # WITNESS EXTRACTION (DETERMINISTIC)
    # -------------------------------------------------
    witnesses = []

    for s in statements:

        witness = (
            s.get("witness")
            if isinstance(s, dict)
            else getattr(s, "witness", None)
        )

        if witness:
            witnesses.append(
                str(witness).strip()
            )

    witnesses = sorted(set(witnesses))

    # -------------------------------------------------
    # EVENT → WITNESSES
    # -------------------------------------------------
    event_to_witnesses = {}

    for e in timeline:

        normalized = _deep_normalize(e)

        event_id = normalized.get(
            "event_id"
        )

        event_to_witnesses[event_id] = [
            str(w).strip()
            for w in normalized.get(
                "witnesses",
                []
            )
        ]

    payloads = []

    for witness in witnesses:

        witness_key = (
            str(witness)
            .strip()
            .lower()
        )

        # -------------------------------------------------
        # STATEMENTS
        # -------------------------------------------------
        witness_statements = []

        for s in statements:

            normalized = _deep_normalize(s)

            sw = (
                str(
                    normalized.get(
                        "witness",
                        ""
                    )
                )
                .strip()
                .lower()
            )

            if sw == witness_key:
                witness_statements.append(
                    normalized
                )

        statement_ids = {

            str(
                s["statement_id"]
            ).strip()

            for s
            in witness_statements

            if s.get(
                "statement_id"
            )
        }

        # -------------------------------------------------
        # CONTRADICTIONS
        # -------------------------------------------------
        witness_contradictions = []

        seen_pairs = set()

        for c in contradictions:

            normalized = (
                _deep_normalize(c)
            )

            event_ids = tuple(
                sorted(
                    normalized.get(
                        "event_ids",
                        []
                    )
                )
            )

            if (
                not event_ids
                or event_ids
                in seen_pairs
            ):
                continue

            involved = set()

            for eid in event_ids:

                involved.update(
                    event_to_witnesses.get(
                        eid,
                        []
                    )
                )

            involved = {
                x.lower().strip()
                for x in involved
            }

            if witness_key in involved:

                witness_contradictions.append(
                    normalized
                )

                seen_pairs.add(
                    event_ids
                )

        # -------------------------------------------------
        # BEHAVIOR
        # -------------------------------------------------
        witness_behavior = []

        for b in behavior_report:

            normalized = (
                _deep_normalize(b)
            )

            explanation = (
                normalized.get(
                    "explanation",
                    ""
                )
                .lower()
            )

            attach = False

            if any(
                sid.lower()
                in explanation
                for sid
                in statement_ids
            ):
                attach = True

            elif (
                witness_key
                in explanation
            ):
                attach = True

            if attach:

                witness_behavior.append(
                    normalized
                )

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

    for i, (witness, witness_key, payload) in enumerate(payloads, 1):

        log.info(f"[credibility] ({i}/{len(payloads)}) Grading: {witness}")

        try:

            result = (
                await
                CredibilityOfInformationAgent()
                .run(payload)
            )

            # ---------------------------------------------
            # OUTPUT VALIDATION
            # ---------------------------------------------
            returned = (
                str(result.witness)
                .strip()
            )

            if not returned:
                raise ValueError("Missing witness")

            if returned.lower() != witness_key:
                raise ValueError(
                    f"Witness mismatch {returned}"
                )

            if not result.evidence:
                raise ValueError("Evidence missing")

            # ---------------------------------------------
            # DETERMINISTIC GRADING (PYTHON MATH)
            # ---------------------------------------------
            metrics = result.metrics.model_dump()

            # Safely extract floats (default to 0.0 if something goes wrong)
            ic = float(metrics.get("internal_consistency", 0.0))
            cc = float(metrics.get("cross_confirmation", 0.0))
            dq = float(metrics.get("detail_quality", 0.0))
            oq = float(metrics.get("observation_quality", 0.0))
            ca = float(metrics.get("contextual_alignment", 0.0))

            weighted_score = (
                (0.25 * ic) +
                (0.20 * cc) +
                (0.20 * dq) +
                (0.15 * oq) +
                (0.20 * ca)
            )

            if weighted_score >= 0.80:
                grade = 1
            elif weighted_score >= 0.65:
                grade = 2
            elif weighted_score >= 0.50:
                grade = 3
            elif weighted_score >= 0.35:
                grade = 4
            elif weighted_score >= 0.15:
                grade = 5
            else:
                grade = 6

            log.info(f"[credibility] ({i}/{len(payloads)}) {witness} → score: {weighted_score:.3f} → grade {grade}")

            results.append({

                "witness":
                    returned,

                "evidence": [
                    e.model_dump()
                    for e in result.evidence
                ],

                "metrics":
                    metrics,

                "credibility_grade":
                    grade,
                
                "weighted_score":
                    round(weighted_score, 3)
            })

        except Exception as e:

            log.warning(f"[credibility] ({i}/{len(payloads)}) {witness} → FAILED: {e}")

            results.append({

                "witness":
                    witness,

                "evidence":
                    [],

                "metrics":
                    None,

                "credibility_grade":
                    6,

                "error":
                    str(e)
            })

    log.info(f"[credibility] Done — {len(results)} witnesses graded")
    _save_debug("credibility_metrics.json", results)
    return {
        "credibility_metrics": results
    }


# =========================
# RELIABILITY OF SOURCE NODE
# =========================

async def reliability_node(state):

    payloads = _build_witness_payloads(state)
    log.info(f"[reliability] Starting — {len(payloads)} witnesses to grade (A-F scale)")

    results = []

    for i, (witness, witness_key, payload) in enumerate(payloads, 1):

        log.info(f"[reliability] ({i}/{len(payloads)}) Grading: {witness}")

        try:

            result = (
                await
                ReliabilityOfSourceAgent()
                .run(payload)
            )

            # ---------------------------------------------
            # OUTPUT VALIDATION
            # ---------------------------------------------
            returned = (
                str(result.witness)
                .strip()
            )

            if not returned:
                raise ValueError("Missing witness")

            if returned.lower() != witness_key:
                raise ValueError(
                    f"Witness mismatch {returned}"
                )

            if result.grade not in ("A", "B", "C", "D", "E", "F"):
                raise ValueError(
                    f"Invalid reliability grade: {result.grade}"
                )

            if not result.explanation:
                raise ValueError("Missing explanation")

            if not result.factors_assessed:
                raise ValueError("Missing factors_assessed")

            log.info(f"[reliability] ({i}/{len(payloads)}) {witness} → grade {result.grade}")

            results.append({

                "witness":
                    returned,

                "grade":
                    result.grade,

                "explanation":
                    result.explanation,

                "factors_assessed":
                    result.factors_assessed
            })

        except Exception as e:

            log.warning(f"[reliability] ({i}/{len(payloads)}) {witness} → FAILED: {e}")

            results.append({

                "witness":
                    witness,

                "grade":
                    "F",

                "explanation":
                    "Reliability of source evaluation failed.",

                "factors_assessed":
                    [str(e)]
            })

    log.info(f"[reliability] Done — {len(results)} witnesses graded")
    _save_debug("reliability_grades.json", results)
    return {
        "reliability_grades": results
    }


# =========================
# REPORT NODE
# =========================

async def report_node(state):

    log.info("[report] Assembling final report")

    report = {

        "timeline":
            _deep_normalize(
                state.timeline
            ),

        "contradictions":
            _deep_normalize(
                state.contradictions
            ),

        "attributes":
            _deep_normalize(
                state.attributes
            ),

        "behavior_report":
            _deep_normalize(
                state.behavior_report
            ),

        "credibility_metrics":
            _deep_normalize(
                state.credibility_metrics
            ),

        "reliability_grades":
            _deep_normalize(
                state.reliability_grades
            ),

        "debug_trace":
            _deep_normalize(
                getattr(
                    state,
                    "debug_trace",
                    []
                )
            )
    }

    log.info("[report] Done — final report ready")

    return {
        "final_report":
            report
    }
