package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/Pepitodrop/signalchord/services/internal/configcheck"
	"github.com/Pepitodrop/signalchord/services/internal/events"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
	"github.com/google/uuid"
	"github.com/mmcdole/gofeed"
)

type sourcePolicy struct {
	SourceID            string   `json:"source_id"`
	RightsStatus        string   `json:"rights_status"`
	Owner               string   `json:"owner"`
	LegalBasis          string   `json:"legal_basis"`
	PermittedUses       []string `json:"permitted_uses"`
	Attribution         string   `json:"attribution"`
	TermsStatus         string   `json:"terms_status"`
	Geography           string   `json:"geography"`
	RetentionDays       int      `json:"retention_days"`
	DeletionObligations string   `json:"deletion_obligations"`
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := configcheck.RequireProduction(configcheck.CurrentEnv(), configcheck.Kafka(), configcheck.HTTPSURL("CONTROL_PLANE_URL")); err != nil {
		logger.Error("validate production config", "error", err)
		os.Exit(1)
	}
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:29092"), ",")
	producer, err := kafkautil.NewProducer(brokers)
	if err != nil {
		logger.Error("kafka producer", "error", err)
		os.Exit(1)
	}
	defer producer.Close()
	feedURL := env("FEED_URL", "https://example.com/feed.xml")
	sourceID := env("SOURCE_ID", "sample-rss")
	policy, err := loadSourcePolicy(sourceID)
	if err != nil {
		logger.Error("source policy rejected", "source_id", sourceID, "error", err)
		os.Exit(1)
	}
	if err := poll(ctx, logger, producer, feedURL, sourceID, policy); err != nil {
		logger.Error("poll failed", "url", feedURL, "error", err)
		os.Exit(1)
	}
}

func poll(ctx context.Context, logger *slog.Logger, producer *kafkautil.Producer, feedURL string, sourceID string, policy sourcePolicy) error {
	feed, err := gofeed.NewParser().ParseURLWithContext(feedURL, ctx)
	if err != nil {
		return err
	}
	for _, item := range feed.Items {
		if item.Link == "" {
			continue
		}
		h := sha256.Sum256([]byte(strings.TrimSpace(strings.ToLower(item.Link))))
		key := hex.EncodeToString(h[:])
		correlationID := uuid.NewString()
		payload := events.DocumentDiscovered{SourceID: sourceID, URL: item.Link, CanonicalURLHash: key, Title: item.Title, PublishedAt: item.PublishedParsed, FetchPolicyID: env("FETCH_POLICY_ID", "public-rss-default")}
		envelope := events.Envelope[events.DocumentDiscovered]{EventID: uuid.NewString(), EventType: "source.document.discovered.v1", SchemaVersion: 1, TenantID: env("SIGNALCHORD_TENANT_ID", "tenant-demo"), OccurredAt: sourceTime(item.PublishedParsed), IngestedAt: time.Now().UTC(), CorrelationID: correlationID, Origin: "feed-collector", ProcessingStage: "discovery", IdempotencyKey: "discover:" + key, Payload: payload}
		envelope.Attributes = sourcePolicyAttributes(policy)
		if err := producer.PublishJSON(ctx, "source.document.discovered.v1", key, envelope); err != nil {
			return err
		}
		logger.Info("document discovered", "url", item.Link, "correlation_id", correlationID)
	}
	return nil
}

func sourceTime(t *time.Time) time.Time {
	if t != nil {
		return t.UTC()
	}
	return time.Now().UTC()
}

func loadSourcePolicy(sourceID string) (sourcePolicy, error) {
	raw := os.Getenv("SOURCE_POLICY_JSON")
	if raw == "" {
		if env("SIGNALCHORD_ENV", "development") == "production" {
			return sourcePolicy{}, fmt.Errorf("SOURCE_POLICY_JSON is required in production")
		}
		return sourcePolicy{
			SourceID:            sourceID,
			RightsStatus:        "approved",
			Owner:               "local-development",
			LegalBasis:          "synthetic-fixture",
			PermittedUses:       []string{"development-test"},
			Attribution:         "Synthetic local fixture",
			TermsStatus:         "first_party_fixture",
			Geography:           "local",
			RetentionDays:       30,
			DeletionObligations: "delete-on-reset",
		}, nil
	}
	var policy sourcePolicy
	if err := json.Unmarshal([]byte(raw), &policy); err != nil {
		return sourcePolicy{}, err
	}
	if policy.SourceID != sourceID {
		return sourcePolicy{}, fmt.Errorf("source policy id %q does not match SOURCE_ID %q", policy.SourceID, sourceID)
	}
	if policy.RightsStatus != "approved" {
		return sourcePolicy{}, fmt.Errorf("source policy rights_status must be approved")
	}
	if policy.Owner == "" || policy.LegalBasis == "" || policy.Attribution == "" || policy.TermsStatus == "" || policy.Geography == "" || policy.DeletionObligations == "" || len(policy.PermittedUses) == 0 || policy.RetentionDays < 0 {
		return sourcePolicy{}, fmt.Errorf("source policy is missing required inventory fields")
	}
	return policy, nil
}

func sourcePolicyAttributes(policy sourcePolicy) map[string]string {
	return map[string]string{
		"source_policy.rights_status":   policy.RightsStatus,
		"source_policy.owner":           policy.Owner,
		"source_policy.legal_basis":     policy.LegalBasis,
		"source_policy.attribution":     policy.Attribution,
		"source_policy.terms_status":    policy.TermsStatus,
		"source_policy.geography":       policy.Geography,
		"source_policy.retention_days":  fmt.Sprintf("%d", policy.RetentionDays),
		"source_policy.permitted_uses":  strings.Join(policy.PermittedUses, ","),
		"source_policy.deletion_policy": policy.DeletionObligations,
	}
}

func env(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
