from pydantic import BaseModel
from typing import List, Optional

class CredibilityMetrics(BaseModel):
    internal_consistency: float
    physical_impossibility: float
    orchestration_marker: float
    detail_quality: float

class CredibilitySignal(BaseModel):
    type: str
    description: str
    score: float

class CredibilityResult(BaseModel):
    witness: str
    evidence: List[CredibilitySignal]
    metrics: Optional[CredibilityMetrics] = None