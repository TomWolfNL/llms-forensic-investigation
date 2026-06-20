from pydantic import BaseModel


class CredibilityScore(
    BaseModel
):

    witness: str

    grade: str

    explanation: str

    evidence_used: list[str]


class CredibilityResult(BaseModel):
    witness: str
    grade: str
    score: float
    explanation: str
    evidence_used: list[str]