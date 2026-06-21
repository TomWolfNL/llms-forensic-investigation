# =========================
# CORE PIPELINE NODES
# =========================

from agents.timeline_agent import TimelineAgent
from agents.attribute_agent import AttributeAgent
from agents.behavioral_agent import BehavioralConsistencyAgent
from agents.contradiction_agent import TimelineContradictionAgent

from agents.reliability_agent import ReliabilityEvidenceAgent
from agents.credibility_agent import CredibilityAgent

from utils.reporter import build_report

import json
from typing import Any, Dict


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


def _normalize_reliability_output(data: Dict[str, Any]) -> list:
    """
    MUST return LIST (FinalReport expects list)
    """

    if not isinstance(data, dict):
        return []

    items = data.get("reliability", [])

    normalized = []

    for item in items:
        metrics = item.get("metrics", {}) or {}

        normalized.append({
            "type": item.get("type", "unknown"),
            "witness": item.get("witness", "unknown"),
            "total_score": _safe_float(item.get("total_score", item.get("score", 0.0))),
            "metrics": {
                "internal_consistency": _safe_float(metrics.get("internal_consistency")),
                "cross_confirmation": _safe_float(metrics.get("cross_confirmation")),
                "detail_quality": _safe_float(metrics.get("detail_quality")),
                "observation_quality": _safe_float(metrics.get("observation_quality")),
                "contextual_alignment": _safe_float(metrics.get("contextual_alignment")),
            }
        })

    return normalized


def _normalize_credibility(result: Any) -> list:
    """
    MUST match FinalReport.CredibilityScore schema
    """

    if isinstance(result, dict):
        score = _safe_float(result.get("score", result.get("credibility", 0.0)))
    else:
        score = _safe_float(result)

    score = max(0.0, min(1.0, score))

    return [
        {
            "grade": "SYSTEM",
            "score": score,
            "evidence_used": "Aggregated from reliability analysis"
        }
    ]


# =========================
# PIPELINE NODES
# =========================

async def timeline_node(state):
    result = await TimelineAgent().run(state.statements)
    return {"timeline": result}


async def attribute_node(state):
    result = await AttributeAgent().run(state.statements)
    return {"attributes": result}


async def contradiction_node(state):
    result = await TimelineContradictionAgent().run(state.timeline)
    return {"contradictions": result}


async def behavioral_node(state):
    result = result = await BehavioralConsistencyAgent().run(
        state.statements,
        state.attributes
    )
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
    Runs BEFORE reliability node (or after behavior node depending on wiring).
    """

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

    return state


async def reliability_node(state):

    results = []

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

    # =================================================
    # PER WITNESS
    # =================================================
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
        # FIX:
        # deduplicate same event pair
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
        # FIX:
        # NEVER map person -> witness
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

            # statement reference
            if any(
                sid.lower()
                in explanation
                for sid
                in statement_ids
            ):
                attach = True

            # witness mention
            elif (
                witness_key
                in explanation
            ):
                attach = True

            if attach:

                witness_behavior.append(
                    normalized
                )

        # -------------------------------------------------
        # PAYLOAD
        # -------------------------------------------------
        payload = {

            "witness":
                witness,

            "statements":
                witness_statements,

            "contradictions":
                witness_contradictions,

            "behavior":
                witness_behavior
        }

        payload = (
            _deep_normalize(
                payload
            )
        )

        try:

            result = (
                await
                ReliabilityEvidenceAgent()
                .run(
                    payload
                )
            )

            # ---------------------------------------------
            # OUTPUT VALIDATION
            # ---------------------------------------------
            returned = (
                str(
                    result.witness
                )
                .strip()
            )

            if not returned:

                raise ValueError(
                    "Missing witness"
                )

            if (
                returned.lower()
                != witness_key
            ):

                raise ValueError(
                    (
                        "Witness mismatch "
                        f"{returned}"
                    )
                )

            if (
                not result.evidence
            ):

                raise ValueError(
                    "Evidence missing"
                )

            score = float(
                result.total_score
            )

            if (
                score < 0
                or score > 1
            ):

                raise ValueError(
                    "Invalid score"
                )

            results.append({

                "witness":
                    returned,

                "evidence": [

                    e.model_dump()

                    for e
                    in result.evidence
                ],

                "metrics":
                    result.metrics.model_dump(),

                "total_score":
                    round(
                        score,
                        2
                    )
            })

        except Exception as e:

            results.append({

                "witness":
                    witness,

                "evidence":
                    [],

                "metrics":
                    None,

                "total_score":
                    None,

                "error":
                    str(e)
            })

    return {

        "reliability_metrics":
            results
    }


async def credibility_node(state):

    def score_to_grade(score):

        score = round(
            float(score),
            2
        )

        if score >= 0.85:
            return "A"

        if score >= 0.70:
            return "B"

        if score >= 0.55:
            return "C"

        if score >= 0.40:
            return "D"
            

        return "F"

    outputs = []

    for r in (
        state.reliability_metrics
        or []
    ):

        witness = (
            str(
                r.get(
                    "witness"
                )
            )
        )

        reliability_score = (
            r.get(
                "total_score"
            )
        )

        try:

            # --------------------------------
            # reliability failed
            # --------------------------------
            if (
                reliability_score
                is None
                or
                r.get(
                    "metrics"
                )
                is None
            ):

                outputs.append({

                    "witness":
                        witness,

                    "grade":
                        "F",

                    "explanation":
                        (
                            "Credibility unavailable "
                            "because reliability "
                            "evaluation failed."
                        ),

                    "evidence_used":
                        [
                            r.get(
                                "error"
                            )
                            or
                            "reliability failed"
                        ]
                })

                continue

            result = (
                await
                CredibilityAgent()
                .run(r)
            )

            # --------------------------------
            # HARD VALIDATION
            # --------------------------------
            if (
                result.witness
                != witness
            ):
                raise ValueError(
                    (
                        "Witness mismatch: "
                        f"{result.witness}"
                    )
                )

            if (
                not result.explanation
            ):
                raise ValueError(
                    (
                        "Missing "
                        "explanation"
                    )
                )

            if (
                not result.evidence_used
            ):
                raise ValueError(
                    (
                        "Missing "
                        "evidence_used"
                    )
                )

            # --------------------------------
            # clamp LLM score
            # --------------------------------
            model_score = max(
                0.0,
                min(
                    float(
                        result.score
                    ),
                    1.0
                )
            )

            # reject large drift
            if (
                abs(
                    model_score
                    -
                    float(
                        reliability_score
                    )
                )
                >
                0.15
            ):
                model_score = (
                    reliability_score
                )

            outputs.append({

                "witness":
                    witness,

                "grade":
                    score_to_grade(
                        reliability_score
                    ),

                "score":
                    round(
                        reliability_score,
                        2
                    ),

                "explanation":
                    result.explanation,

                "evidence_used":
                    result.evidence_used
            })

        except Exception as e:

            outputs.append({

                "witness":
                    witness,

                "grade":
                    "F",

                "score":
                    0.0,

                "explanation":
                    (
                        "Credibility "
                        "evaluation failed."
                    ),

                "evidence_used":
                    [
                        str(e)
                    ]
            })

    return {

        "credibility_scores":
            outputs
    }


# =========================
# REPORT NODE
# =========================

async def report_node(state):

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

        "reliability_metrics":
            _deep_normalize(
                state.reliability_metrics
            ),

        "credibility_scores":
            _deep_normalize(
                state.credibility_scores
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

    return {
        "final_report":
            report
    }