from pydantic import BaseModel
from typing import Optional


class ExtractedStatement(BaseModel):

    statement_id: str

    witness: str

    subject: Optional[str] = None

    time: Optional[str] = None

    location: Optional[str] = None

    action: Optional[str] = None

    context: Optional[str] = None

    raw_text: str


class ExtractionResult(BaseModel):

    statements: list[ExtractedStatement]
