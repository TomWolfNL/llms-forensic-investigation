from typing import Literal
from pydantic import BaseModel


class Contradiction(BaseModel):

    contradiction_id: str

    type: Literal[
        "time_conflict",
        "location_conflict",
        "action_conflict",
        "identity_conflict",
        "causal_conflict"
    ]

    event_ids: list[str]

    explanation: str

    severity: float


class ContradictionResult(
    BaseModel
):

    contradictions: list[
        Contradiction
    ]