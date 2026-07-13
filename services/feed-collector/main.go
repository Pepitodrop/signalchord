package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/Pepitodrop/signalchord/services/internal/events"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
	"github.com/google/uuid"
	"github.com/mmcdole/gofeed"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:29092"), ",")
	producer, err := kafkautil.NewProducer(brokers)
	if err != nil {
		logger.Error("kafka producer", "error", err)
		os.Exit(1)
	}
	defer producer.Close()
	feedURL := env("FEED_URL", "https://example.com/feed.xml")
	if err := poll(ctx, logger, producer, feedURL); err != nil {
		logger.Error("poll failed", "url", feedURL, "error", err)
		os.Exit(1)
	}
}

func poll(ctx context.Context, logger *slog.Logger, producer *kafkautil.Producer, feedURL string) error {
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
		payload := events.DocumentDiscovered{SourceID: env("SOURCE_ID", "sample-rss"), URL: item.Link, CanonicalURLHash: key, Title: item.Title, PublishedAt: item.PublishedParsed, FetchPolicyID: env("FETCH_POLICY_ID", "public-rss-default")}
		envelope := events.Envelope[events.DocumentDiscovered]{EventID: uuid.NewString(), EventType: "source.document.discovered.v1", SchemaVersion: 1, TenantID: env("SIGNALCHORD_TENANT_ID", "tenant-demo"), OccurredAt: sourceTime(item.PublishedParsed), IngestedAt: time.Now().UTC(), CorrelationID: correlationID, Origin: "feed-collector", ProcessingStage: "discovery", IdempotencyKey: "discover:" + key, Payload: payload}
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

func env(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
