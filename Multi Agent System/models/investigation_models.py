from pydantic import BaseModel
from typing import List


class Statement(BaseModel):
    statement_id: str
    witness: str
    subject: str
    time: str
    location: str
    action: str
    context: str
    raw_text: str


class TimelineEvent(BaseModel):
    event_id: str
    statement_ids: List[str]
    time: str
    location: str
    subject: str
    action: str
    context: str
    witnesses: List[str]


class Contradiction(BaseModel):
    contradiction_id: str
    type: str
    event_ids: List[str]
    explanation: str
    severity: float


class BehavioralIssue(BaseModel):
    issue_id: str
    person: str
    event: str
    explanation: str
    confidence: float


class ReliabilityMetric(BaseModel):
    internal_consistency: float
    cross_confirmation: float
    detail_quality: float
    observation_quality: float
    contextual_alignment: float


class WitnessReliability(BaseModel):
    witness: str
    metrics: ReliabilityMetric
    total_score: float


class GraphState(BaseModel):
    statements: List[Statement]
    timeline: List[TimelineEvent]
    contradictions: List[Contradiction]
    behavior_report: List[BehavioralIssue]
    reliability_metrics: List[WitnessReliability]
    credibility_scores: List[dict]