from __future__ import annotations
from pydantic import BaseModel, Field

class Candidate(BaseModel):
    entity_id: str
    display_name: str
    score: float = Field(ge=0, le=1)
    reasons: list[str]

class Resolution(BaseModel):
    mention_id: str
    accepted_entity_id: str | None
    candidates: list[Candidate]
    requires_review: bool

def resolve(mention_id: str, text: str, aliases: dict[str, str]) -> Resolution:
    normalized = " ".join(text.casefold().split())
    if normalized in aliases:
        entity_id = aliases[normalized]
        return Resolution(mention_id=mention_id, accepted_entity_id=entity_id, candidates=[Candidate(entity_id=entity_id, display_name=text, score=1, reasons=["exact normalized alias"])], requires_review=False)
    return Resolution(mention_id=mention_id, accepted_entity_id=None, candidates=[], requires_review=True)
