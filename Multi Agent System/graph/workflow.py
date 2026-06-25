from langgraph.graph import StateGraph, START, END

from graph.state import InvestigationState

from graph.nodes import (
    extraction_node,
    timeline_node,
    attribute_node,
    contradiction_node,
    behavioral_node,
    credibility_node,
    reliability_node,
    report_node,
    debug_inspector_node
)

# -------------------------------------------------
# SAFE PASS-THROUGH NORMALIZER (Pydantic-safe)
# -------------------------------------------------
def normalize_state(state: InvestigationState):

    # DO NOT convert to dict
    # DO NOT touch internal structure

    if not hasattr(state, "debug_trace") or state.debug_trace is None:
        state.debug_trace = []

    return state


def build_graph():

    graph = StateGraph(InvestigationState)

    # -----------------------------
    # NODES
    # -----------------------------
    graph.add_node("normalize", normalize_state)

    graph.add_node("extraction", extraction_node)

    graph.add_node("timeline", timeline_node)
    graph.add_node("attribute", attribute_node)
    graph.add_node("contradiction", contradiction_node)
    graph.add_node("behavior", behavioral_node)

    graph.add_node("debug_inspector", debug_inspector_node)
    graph.add_node("credibility", credibility_node)
    graph.add_node("reliability", reliability_node)
    graph.add_node("report", report_node)

    # -----------------------------
    # FLOW ARCHITECTURE
    # -----------------------------
    graph.add_edge(START, "normalize")

    graph.add_edge("normalize", "extraction")

    # Extraction feeds both timeline and attribute in parallel
    graph.add_edge("extraction", "timeline")
    graph.add_edge("extraction", "attribute")

    graph.add_edge("timeline", "contradiction")
    graph.add_edge("timeline", "behavior")

    graph.add_edge("attribute", "behavior")

    graph.add_edge("contradiction", "debug_inspector")
    graph.add_edge("behavior", "debug_inspector")

    # Credibility of Information and Reliability of Source run in parallel
    graph.add_edge("debug_inspector", "credibility")
    graph.add_edge("debug_inspector", "reliability")

    graph.add_edge("credibility", "report")
    graph.add_edge("reliability", "report")

    graph.add_edge("report", END)

    return graph.compile()
