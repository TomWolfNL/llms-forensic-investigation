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

            credibility_metrics=state.get(
                "credibility_metrics",
                []
            ),

            reliability_grades=state.get(
                "reliability_grades",
                []
            )
        )
    )

    return (
        report.model_dump()
    )
