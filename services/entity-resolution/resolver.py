from __future__ import annotations

import hashlib
import re
from pydantic import BaseModel, Field

DEFAULT_ALIASES = {
    "acme corporation": "company:acme",
    "northstar labs": "organization:northstar-labs",
    "berlin": "location:berlin",
}


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


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned[:96] or hashlib.sha256(value.encode()).hexdigest()[:24]


def resolve(mention_id: str, text: str, aliases: dict[str, str]) -> Resolution:
    normalized = " ".join(text.casefold().split())
    if normalized in aliases:
        entity_id = aliases[normalized]
        return Resolution(
            mention_id=mention_id,
            accepted_entity_id=entity_id,
            candidates=[
                Candidate(
                    entity_id=entity_id,
                    display_name=text,
                    score=1,
                    reasons=["exact normalized alias"],
                )
            ],
            requires_review=False,
        )
    return Resolution(
        mention_id=mention_id,
        accepted_entity_id=None,
        candidates=[],
        requires_review=True,
    )


def resolve_mention(payload: dict, aliases: dict[str, str] | None = None) -> dict:
    mention_id = payload["mention_id"]
    text = payload["text"]
    entity_type = payload["entity_type"]
    confidence = float(payload.get("confidence", 0))
    result = resolve(mention_id, text, aliases or DEFAULT_ALIASES)
    accepted = result.accepted_entity_id
    requires_review = result.requires_review
    status = "model_verified"
    if accepted is None:
        if confidence >= 0.9:
            accepted = f"{entity_type.casefold()}:{slug(text)}"
            requires_review = False
        else:
            accepted = f"candidate:{hashlib.sha256((entity_type + ':' + text).encode()).hexdigest()[:24]}"
            status = "candidate"
            requires_review = True
    return {
        "mention_id": mention_id,
        "document_id": payload["document_id"],
        "entity_id": accepted,
        "entity_type": entity_type,
        "display_name": text,
        "confidence": confidence,
        "status": status,
        "requires_review": requires_review,
        "alternatives": [candidate.model_dump(mode="json") for candidate in result.candidates],
        "evidence": payload["evidence"],
        "extraction_model": payload.get("extraction_model"),
        "extraction_version": payload.get("extraction_version"),
    }
