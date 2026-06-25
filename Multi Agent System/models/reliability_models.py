from pydantic import BaseModel
from typing import Any


class CredibilityMetrics(BaseModel):

    internal_consistency: float

    cross_confirmation: float

    detail_quality: float

    observation_quality: float

    contextual_alignment: float


class CredibilitySignal(BaseModel):
    type: str
    description: str
    score: float


class CredibilityResult(BaseModel):
    witness: str
    evidence: list[CredibilitySignal]
    metrics: CredibilityMetrics
    credibility_grade: int
