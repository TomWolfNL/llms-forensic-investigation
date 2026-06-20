from pydantic import BaseModel


class AttributeClaim(BaseModel):

    claim: str

    source: str

    confidence: float


class PersonAttributes(BaseModel):

    person: str

    attributes: list[AttributeClaim]


class AttributeResult(BaseModel):

    people: list[PersonAttributes]