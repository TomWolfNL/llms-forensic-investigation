from pydantic import BaseModel
from typing import Optional


class TimelineEvent(BaseModel):

    event_id: str

    statement_ids: list[str]

    time: Optional[str]

    location: Optional[str]

    subject: Optional[str]

    action: Optional[str]

    context: Optional[str]

    witnesses: list[str]


class TimelineResult(BaseModel):

    events: list[TimelineEvent]