from pydantic import BaseModel
from typing import Any

class ReliabilityMetrics(
    BaseModel
):

    internal_consistency: float

    cross_confirmation: float

    detail_quality: float

    observation_quality: float

    contextual_alignment: float


class ReliabilityEvidence(
    BaseModel
):

    witness: str

    metrics: ReliabilityMetrics

    total_score: float


class ReliabilitySignal(BaseModel):
    type: str
    description: str
    score: float


class ReliabilityResult(BaseModel):
    witness: str
    evidence: list[ReliabilitySignal]
    metrics: ReliabilityMetrics
    total_score: float