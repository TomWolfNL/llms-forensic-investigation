from pydantic import BaseModel

from models.timeline_models import TimelineEvent
from models.contradiction_models import Contradiction
from models.attribute_models import PersonAttributes
from models.behavior_models import BehavioralIssue
from models.reliability_models import ReliabilityEvidence
from models.credibility_models import CredibilityScore


class FinalReport(BaseModel):

    timeline: list[TimelineEvent]

    contradictions: list[Contradiction]

    attributes: list[PersonAttributes]

    behavior_report: list[BehavioralIssue]

    reliability: list[ReliabilityEvidence]

    credibility_scores: list[CredibilityScore]