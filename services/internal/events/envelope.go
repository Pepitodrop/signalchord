package events

import (
	"time"

	"github.com/google/uuid"
)

type Envelope[T any] struct {
	EventID         string            `json:"event_id"`
	EventType       string            `json:"event_type"`
	SchemaVersion   int               `json:"schema_version"`
	TenantID        string            `json:"tenant_id"`
	OccurredAt      time.Time         `json:"occurred_at"`
	IngestedAt      time.Time         `json:"ingested_at"`
	CorrelationID   string            `json:"correlation_id"`
	CausationID     string            `json:"causation_id,omitempty"`
	Origin          string            `json:"origin"`
	ProcessingStage string            `json:"processing_stage"`
	IdempotencyKey  string            `json:"idempotency_key"`
	Traceparent     string            `json:"traceparent,omitempty"`
	Attributes      map[string]string `json:"attributes,omitempty"`
	Payload         T                 `json:"payload"`
}

func NewEnvelope[T any](eventType, tenantID, correlationID, causationID, origin, stage, idempotencyKey string, occurredAt time.Time, payload T) Envelope[T] {
	return Envelope[T]{EventID: uuid.NewString(), EventType: eventType, SchemaVersion: 1, TenantID: tenantID, OccurredAt: occurredAt.UTC(), IngestedAt: time.Now().UTC(), CorrelationID: correlationID, CausationID: causationID, Origin: origin, ProcessingStage: stage, IdempotencyKey: idempotencyKey, Payload: payload}
}

type DocumentDiscovered struct {
	SourceID         string     `json:"source_id"`
	URL              string     `json:"url"`
	CanonicalURLHash string     `json:"canonical_url_hash"`
	Title            string     `json:"title"`
	PublishedAt      *time.Time `json:"published_at,omitempty"`
	FetchPolicyID    string     `json:"fetch_policy_id"`
}

type DocumentFetched struct {
	DocumentID string            `json:"document_id"`
	SourceID   string            `json:"source_id"`
	FinalURL   string            `json:"final_url"`
	ContentHash string           `json:"content_hash"`
	ObjectURI  string            `json:"object_uri"`
	MediaType  string            `json:"media_type"`
	Charset    string            `json:"charset"`
	HTTPStatus int               `json:"http_status"`
	HTTPHeaders map[string]string `json:"http_headers"`
}

type NormalizedDocument struct {
	DocumentID        string     `json:"document_id"`
	CanonicalURL      string     `json:"canonical_url"`
	Title             string     `json:"title"`
	CleanTextObjectURI string    `json:"clean_text_object_uri"`
	PublishedAt       *time.Time `json:"published_at,omitempty"`
	LanguageHint      string     `json:"language_hint,omitempty"`
	ContentHash       string     `json:"content_hash"`
}

type DuplicateDetected struct {
	DocumentID          string `json:"document_id"`
	CanonicalDocumentID string `json:"canonical_document_id"`
	ContentHash         string `json:"content_hash"`
	Method              string `json:"method"`
}
