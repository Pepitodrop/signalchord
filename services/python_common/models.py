from __future__ import annotations
from datetime import datetime
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class Envelope(BaseModel, Generic[T]):
    event_id: str
    event_type: str
    schema_version: int = 1
    tenant_id: str
    occurred_at: datetime
    ingested_at: datetime
    correlation_id: str
    causation_id: str | None = None
    origin: str
    processing_stage: str
    idempotency_key: str
    traceparent: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    payload: T
