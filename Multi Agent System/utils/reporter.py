from models.report_models import (
    FinalReport
)


def build_report(
    state
):

    report = (
        FinalReport(
            timeline=state.get(
                "timeline",
                []
            ),

            contradictions=state.get(
                "contradictions",
                []
            ),

            attributes=state.get(
                "attributes",
                []
            ),

            behavior_report=state.get(
                "behavior_report",
                []
            ),

            reliability=state.get(
                "reliability_metrics",
                []
            ),

            credibility_scores=state.get(
                "credibility_scores",
                []
            )
        )
    )

    return (
        report.model_dump()
    )