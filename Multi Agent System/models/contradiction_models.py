from typing import Literal
from pydantic import BaseModel, Field


class Contradiction(BaseModel):
    contradiction_id: str
    type: Literal[
        "time_conflict",
        "location_conflict",
        "action_conflict",
        "identity_conflict",
        "causal_conflict",
        "physical_evidence_conflict"
    ]
    event_ids: list[str]
    explanation: str
    severity: float


class ContradictionResult(BaseModel):
    analysis_scratchpad: str = Field(
        description="Step-by-step reasoning before finalizing contradictions"
    )
    contradictions: list[Contradiction]