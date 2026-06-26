import operator
from typing import List, Optional, Dict, Annotated, Any
from pydantic import BaseModel, Field

from models.timeline_models import TimelineEvent
from models.contradiction_models import Contradiction
from models.attribute_models import PersonAttributes
from models.behavior_models import BehavioralIssue
from models.reliability_models import CredibilityResult
from models.credibility_models import ReliabilityResult
from models.investigation_models import Statement


class InvestigationState(BaseModel):
    debug_trace: list = Field(default_factory=list)
    raw_story: Dict = Field(default_factory=dict)
    statements: List = Field(default_factory=list)
    timeline: List = Field(default_factory=list)
    contradictions: List = Field(default_factory=list)
    attributes: List = Field(default_factory=list)
    behavior_report: List = Field(default_factory=list)
    credibility_metrics: List = Field(default_factory=list)
    reliability_grades: List = Field(default_factory=list)
    final_report: Dict = Field(default_factory=dict)
    telemetry_log: Annotated[List[Dict[str, Any]], operator.add] = Field(default_factory=list)