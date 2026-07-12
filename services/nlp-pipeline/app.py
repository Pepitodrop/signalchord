from __future__ import annotations

import hashlib
import math
import re
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SignalChord NLP Pipeline", version="1.0.0")


class Document(BaseModel):
    document_id: str
    text: str = Field(min_length=1, max_length=2_000_000)
    language_hint: str | None = None


class Evidence(BaseModel):
    evidence_id: str
    document_id: str
    start_offset: int
    end_offset: int
    span_hash: str


class Mention(BaseModel):
    mention_id: str
    text: str
    entity_type: Literal["Person", "Organization", "Company", "GovernmentAgency", "Location"]
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class Claim(BaseModel):
    claim_id: str
    proposition: str
    stance: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class Relation(BaseModel):
    relationship_id: str
    subject_mention_id: str
    predicate: Literal[
        "PARTNERED_WITH",
        "ACQUIRED",
        "INVESTED_IN",
        "COMPETES_WITH",
        "REGULATES",
        "AFFECTS",
        "RELATED_TO",
    ]
    object_mention_id: str
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence


class Extraction(BaseModel):
    language: str
    extraction_model: str = "signalchord-rules"
    extraction_version: str = "1.0.0"
    embedding_model: str = "signalchord-hash-embedding-1"
    mentions: list[Mention]
    claims: list[Claim]
    relations: list[Relation]
    topics: list[str]
    embedding: list[float]


COMPANY = re.compile(
    r"\b(?:[A-Z][\w&.-]+(?:\s+|$)){1,4}(?:Inc\.?|Corp(?:oration)?\.?|Ltd\.?|LLC|PLC)\b"
)
ORGANIZATION = re.compile(
    r"\b(?:[A-Z][\w&.-]+(?:\s+|$)){1,4}(?:Labs?|University|Institute|Association|Foundation)\b"
)
AGENCY = re.compile(
    r"\b(?:[A-Z][\w&.-]+(?:\s+|$)){1,5}(?:Agency|Commission|Ministry|Authority|Department)\b"
)
PERSON = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\b")
LOCATION = re.compile(
    r"\b(?:Berlin|Karlsruhe|London|Paris|Singapore|New York|Brussels|Cologne|Munich|Tokyo|Washington)\b"
)
CLAIM = re.compile(
    r"[^.!?]*(?:announced|said|reported|plans?|expects?|denied|confirmed|claimed|warned|agreed)[^.!?]*[.!?]",
    re.I,
)
SENTENCE = re.compile(r"[^.!?]+[.!?]?")
TOPIC_KEYWORDS = {
    "partnerships": {"partnership", "partnered", "collaboration", "alliance"},
    "mergers-and-acquisitions": {"acquired", "acquisition", "merger", "takeover"},
    "investment": {"invested", "funding", "financing", "venture"},
    "regulation": {"regulates", "regulation", "authority", "commission"},
    "technology": {"technology", "software", "platform", "artificial intelligence", "ai"},
    "logistics": {"logistics", "shipping", "supply chain", "warehouse"},
}
RELATION_KEYWORDS = {
    "PARTNERED_WITH": {"partnership", "partnered", "collaboration", "alliance"},
    "ACQUIRED": {"acquired", "acquisition", "bought"},
    "INVESTED_IN": {"invested", "investment", "funding"},
    "COMPETES_WITH": {"competes", "rival", "competitor"},
    "REGULATES": {"regulates", "sanctioned", "approved"},
    "AFFECTS": {"affects", "impacts", "disrupted"},
}
NEGATIVE = {"denied", "not", "never", "no", "warned", "failed"}
POSITIVE = {"confirmed", "agreed", "announced", "expects", "plans"}


def evidence(document_id: str, text: str, start: int, end: int) -> Evidence:
    span = text[start:end]
    digest = hashlib.sha256(span.encode()).hexdigest()
    return Evidence(
        evidence_id=f"ev:{document_id}:{start}:{end}",
        document_id=document_id,
        start_offset=start,
        end_offset=end,
        span_hash=digest,
    )


def hash_embedding(text: str, dimensions: int = 32) -> list[float]:
    values = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.casefold()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        values[index] += sign
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [round(value / norm, 6) for value in values]


def stance(text: str) -> Literal["positive", "negative", "neutral"]:
    tokens = set(re.findall(r"[a-z]+", text.casefold()))
    if tokens.intersection(NEGATIVE):
        return "negative"
    if tokens.intersection(POSITIVE):
        return "positive"
    return "neutral"


def extract_mentions(doc: Document) -> list[Mention]:
    candidates: list[tuple[int, int, str, str, float]] = []
    patterns = [
        ("Company", COMPANY, 0.94),
        ("GovernmentAgency", AGENCY, 0.93),
        ("Organization", ORGANIZATION, 0.91),
        ("Location", LOCATION, 0.97),
        ("Person", PERSON, 0.83),
    ]
    for entity_type, pattern, confidence in patterns:
        for match in pattern.finditer(doc.text):
            candidates.append((match.start(), match.end(), entity_type, match.group().strip(), confidence))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), -item[4]))
    accepted: list[tuple[int, int]] = []
    mentions: list[Mention] = []
    for start, end, entity_type, value, confidence in candidates:
        if any(start < existing_end and end > existing_start for existing_start, existing_end in accepted):
            continue
        accepted.append((start, end))
        ev = evidence(doc.document_id, doc.text, start, end)
        mentions.append(
            Mention(
                mention_id=f"mention:{ev.evidence_id}",
                text=value,
                entity_type=entity_type,
                confidence=confidence,
                evidence=ev,
            )
        )
    return mentions


def extract_claims(doc: Document) -> list[Claim]:
    claims: list[Claim] = []
    for match in CLAIM.finditer(doc.text):
        ev = evidence(doc.document_id, doc.text, match.start(), match.end())
        proposition = " ".join(match.group().split())
        claims.append(
            Claim(
                claim_id=f"claim:{ev.span_hash[:24]}",
                proposition=proposition,
                stance=stance(proposition),
                confidence=0.78,
                evidence=ev,
            )
        )
    return claims


def extract_relations(doc: Document, mentions: list[Mention]) -> list[Relation]:
    relations: list[Relation] = []
    for sentence_match in SENTENCE.finditer(doc.text):
        sentence = sentence_match.group()
        lowered = sentence.casefold()
        sentence_mentions = [
            mention
            for mention in mentions
            if mention.evidence.start_offset >= sentence_match.start()
            and mention.evidence.end_offset <= sentence_match.end()
        ]
        if len(sentence_mentions) < 2:
            continue
        predicate = next(
            (
                name
                for name, keywords in RELATION_KEYWORDS.items()
                if any(keyword in lowered for keyword in keywords)
            ),
            None,
        )
        if predicate is None:
            continue
        subject, object_ = sentence_mentions[0], sentence_mentions[1]
        ev = evidence(doc.document_id, doc.text, sentence_match.start(), sentence_match.end())
        relation_hash = hashlib.sha256(
            f"{subject.mention_id}:{predicate}:{object_.mention_id}:{ev.span_hash}".encode()
        ).hexdigest()[:24]
        relations.append(
            Relation(
                relationship_id=f"relationship:{relation_hash}",
                subject_mention_id=subject.mention_id,
                predicate=predicate,
                object_mention_id=object_.mention_id,
                confidence=0.74,
                evidence=ev,
            )
        )
    return relations


def classify_topics(text: str) -> list[str]:
    lowered = text.casefold()
    return sorted(
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    )


def extract(doc: Document) -> Extraction:
    clean_text = " ".join(doc.text.split())
    normalized = Document(document_id=doc.document_id, text=clean_text, language_hint=doc.language_hint)
    mentions = extract_mentions(normalized)
    claims = extract_claims(normalized)
    relations = extract_relations(normalized, mentions)
    return Extraction(
        language=doc.language_hint or "en",
        mentions=mentions,
        claims=claims,
        relations=relations,
        topics=classify_topics(clean_text),
        embedding=hash_embedding(clean_text),
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/v1/extract", response_model=Extraction)
def extract_endpoint(doc: Document) -> Extraction:
    return extract(doc)
