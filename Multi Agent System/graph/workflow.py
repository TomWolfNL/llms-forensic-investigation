from langgraph.graph import StateGraph, START, END

from graph.state import InvestigationState

from graph.nodes import (
    timeline_node,
    attribute_node,
    contradiction_node,
    behavioral_node,
    reliability_node,
    credibility_node,
    report_node,
    debug_inspector_node
)

# -------------------------------------------------
# SAFE PASS-THROUGH NORMALIZER (Pydantic-safe)
# -------------------------------------------------
def normalize_state(state: InvestigationState):

    # DO NOT convert to dict
    # DO NOT touch internal structure

    # Optional: initialize debug trace if missing
    if not hasattr(state, "debug_trace") or state.debug_trace is None:
        state.debug_trace = []

    return state


def build_graph():

    graph = StateGraph(InvestigationState)

    # -----------------------------
    # NODES
    # -----------------------------
    graph.add_node("normalize", normalize_state)

    graph.add_node("timeline", timeline_node)
    graph.add_node("attribute", attribute_node)
    graph.add_node("contradiction", contradiction_node)
    graph.add_node("behavior", behavioral_node)

    graph.add_node("reliability", reliability_node)
    graph.add_node("debug_inspector", debug_inspector_node)
    graph.add_node("credibility", credibility_node)
    graph.add_node("report", report_node)

    # -----------------------------
    # FLOW ARCHITECTURE
    # -----------------------------
    graph.add_edge(START, "normalize")

    graph.add_edge("normalize", "timeline")
    graph.add_edge("normalize", "attribute")

    graph.add_edge("timeline", "contradiction")
    graph.add_edge("timeline", "behavior")

    graph.add_edge("attribute", "behavior")

    graph.add_edge("contradiction", "reliability")
    graph.add_edge("behavior", "reliability")

    # debug inspector AFTER reliability
    graph.add_edge("reliability", "debug_inspector")

    graph.add_edge("debug_inspector", "credibility")

    graph.add_edge("credibility", "report")
    graph.add_edge("report", END)

    return graph.compile()