package events

import "time"

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

type DocumentDiscovered struct {
	SourceID         string     `json:"source_id"`
	URL              string     `json:"url"`
	CanonicalURLHash string     `json:"canonical_url_hash"`
	Title            string     `json:"title"`
	PublishedAt      *time.Time `json:"published_at,omitempty"`
	FetchPolicyID    string     `json:"fetch_policy_id"`
}
