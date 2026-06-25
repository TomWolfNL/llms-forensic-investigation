from pydantic import BaseModel


class ReliabilityResult(BaseModel):
    witness: str
    grade: str
    explanation: str
    factors_assessed: list[str]
