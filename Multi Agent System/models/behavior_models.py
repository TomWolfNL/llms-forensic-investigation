from pydantic import BaseModel


class BehavioralIssue(
    BaseModel
):

    issue_id: str

    person: str

    event: str

    explanation: str

    confidence: float


class BehaviorResult(
    BaseModel
):

    issues: list[
        BehavioralIssue
    ]