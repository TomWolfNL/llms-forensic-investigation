from typing import Literal
from pydantic import BaseModel, Field


class BehavioralIssue(BaseModel):

    issue_id: str

    person: str

    behavior_type: Literal[
        "retraction",
        "motive_alignment",
        "unnatural_access",
        "evasion",
        "innocent_concealment",
        "consistent"
    ]

    explanation: str

    risk_score: float


class BehaviorResult(BaseModel):

    analysis_scratchpad: str = Field(
        description="Step-by-step reasoning evaluating motives, access, and relationships before finalizing issues."
    )

    issues: list[BehavioralIssue]
