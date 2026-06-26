from pydantic import BaseModel, Field
from typing import List


class WitnessEvaluation(BaseModel):
    witness: str
    reliability_grade: str  # A-F
    credibility_grade: int  # 1-6
    reasoning: str
    prime_suspect_likelihood: float = Field(default=0.0, ge=0.0, le=1.0)


class BaselineResult(BaseModel):
    evaluations: List[WitnessEvaluation]
    final_case_summary: str