from pydantic import BaseModel
from typing import Optional


class WitnessStatement(BaseModel):

    statement_id: str

    witness: str

    subject: Optional[str]

    time: Optional[str]

    location: Optional[str]

    action: Optional[str]

    context: Optional[str]

    raw_text: str