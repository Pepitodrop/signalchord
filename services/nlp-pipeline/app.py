from __future__ import annotations
import hashlib
import re
from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SignalChord NLP Pipeline", version="0.1.0")

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
    entity_type: Literal["Person", "Organization", "Location"]
    confidence: float
    evidence: Evidence

class Claim(BaseModel):
    claim_id: str
    proposition: str
    confidence: float
    evidence: Evidence

class Extraction(BaseModel):
    language: str
    extraction_model: str = "signalchord-rules"
    extraction_version: str = "0.1.0"
    mentions: list[Mention]
    claims: list[Claim]

ORG = re.compile(r"\b(?:[A-Z][\w&.-]+(?:\s+|$)){1,4}(?:Inc\.?|Corp(?:oration)?\.?|Ltd\.?|Labs?|University|Agency)\b")
PERSON = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")
LOCATION = re.compile(r"\b(?:Berlin|Karlsruhe|London|Paris|Singapore|New York|Brussels)\b")
CLAIM = re.compile(r"[^.!?]*(?:announced|said|reported|plans|expects|denied|confirmed)[^.!?]*[.!?]", re.I)

def evidence(document_id: str, text: str, start: int, end: int) -> Evidence:
    span = text[start:end]
    digest = hashlib.sha256(span.encode()).hexdigest()
    return Evidence(evidence_id=f"ev:{document_id}:{start}:{end}", document_id=document_id, start_offset=start, end_offset=end, span_hash=digest)

def extract(doc: Document) -> Extraction:
    mentions: list[Mention] = []
    for entity_type, pattern, confidence in [("Organization", ORG, .90), ("Person", PERSON, .82), ("Location", LOCATION, .96)]:
        for match in pattern.finditer(doc.text):
            ev = evidence(doc.document_id, doc.text, match.start(), match.end())
            mentions.append(Mention(mention_id=f"mention:{ev.evidence_id}", text=match.group().strip(), entity_type=entity_type, confidence=confidence, evidence=ev))
    claims: list[Claim] = []
    for match in CLAIM.finditer(doc.text):
        ev = evidence(doc.document_id, doc.text, match.start(), match.end())
        proposition = " ".join(match.group().split())
        claims.append(Claim(claim_id=f"claim:{ev.span_hash[:24]}", proposition=proposition, confidence=.72, evidence=ev))
    return Extraction(language=doc.language_hint or "en", mentions=mentions, claims=claims)

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/v1/extract", response_model=Extraction)
def extract_endpoint(doc: Document) -> Extraction:
    return extract(doc)
