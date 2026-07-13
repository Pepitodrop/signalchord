package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/IBM/sarama"
	"github.com/Pepitodrop/signalchord/services/internal/events"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
	streamnormalizer "github.com/Pepitodrop/signalchord/services/stream-normalizer"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/redis/go-redis/v9"
	"golang.org/x/net/html"
)

const maxNormalizeBytes = 10 << 20

type app struct {
	logger   *slog.Logger
	producer *kafkautil.Producer
	objects  *minio.Client
	redis    *redis.Client
	bucket   string
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:29092"), ",")
	producer, err := kafkautil.NewProducer(brokers)
	fatal(logger, "create producer", err)
	defer producer.Close()
	objects, err := minio.New(env("MINIO_ENDPOINT", "localhost:9000"), &minio.Options{Creds: credentials.NewStaticV4(env("MINIO_ACCESS_KEY", "signalchord"), env("MINIO_SECRET_KEY", "signalchord-dev-secret"), ""), Secure: envBool("MINIO_SECURE", false)})
	fatal(logger, "create object client", err)
	redisOptions, err := redis.ParseURL(env("REDIS_URL", "redis://localhost:6379/0"))
	fatal(logger, "parse redis URL", err)
	application := &app{logger: logger, producer: producer, objects: objects, redis: redis.NewClient(redisOptions), bucket: env("MINIO_BUCKET", "raw-documents")}
	err = kafkautil.Consume(ctx, brokers, "signalchord-stream-normalizer-v1", []string{"source.document.fetched.v1"}, application.handle)
	if err != nil && !errors.Is(err, context.Canceled) {
		fatal(logger, "consume", err)
	}
}

func (a *app) handle(ctx context.Context, message *sarama.ConsumerMessage) error {
	var source events.Envelope[events.DocumentFetched]
	if err := json.Unmarshal(message.Value, &source); err != nil {
		return fmt.Errorf("decode fetched event: %w", err)
	}
	first, err := a.redis.SetNX(ctx, "signalchord:dedupe:"+source.Payload.ContentHash, source.Payload.DocumentID, 90*24*time.Hour).Result()
	if err != nil {
		return fmt.Errorf("dedupe store: %w", err)
	}
	if !first {
		canonicalID, _ := a.redis.Get(ctx, "signalchord:dedupe:"+source.Payload.ContentHash).Result()
		duplicate := events.DuplicateDetected{DocumentID: source.Payload.DocumentID, CanonicalDocumentID: canonicalID, ContentHash: source.Payload.ContentHash, Method: "sha256-exact"}
		envelope := events.NewEnvelope("document.duplicate-detected.v1", source.TenantID, source.CorrelationID, source.EventID, "stream-normalizer", "exact-deduplication", "duplicate:"+source.Payload.DocumentID, source.OccurredAt, duplicate)
		return a.producer.PublishJSON(ctx, "document.duplicate-detected.v1", canonicalID, envelope)
	}
	bucket, objectKey, err := parseObjectURI(source.Payload.ObjectURI)
	if err != nil {
		return err
	}
	object, err := a.objects.GetObject(ctx, bucket, objectKey, minio.GetObjectOptions{})
	if err != nil {
		return err
	}
	defer object.Close()
	body, err := io.ReadAll(io.LimitReader(object, maxNormalizeBytes+1))
	if err != nil {
		return err
	}
	if len(body) > maxNormalizeBytes {
		return errors.New("raw object exceeds normalization limit")
	}
	title, text, err := extractHTML(body)
	if err != nil {
		return fmt.Errorf("extract HTML: %w", err)
	}
	canonicalURL, err := streamnormalizer.CanonicalizeURL(source.Payload.FinalURL)
	if err != nil {
		return err
	}
	cleanKey := fmt.Sprintf("normalized/%s/%s.txt", source.TenantID, strings.TrimPrefix(source.Payload.DocumentID, "doc:"))
	_, err = a.objects.PutObject(ctx, a.bucket, cleanKey, bytes.NewReader([]byte(text)), int64(len(text)), minio.PutObjectOptions{ContentType: "text/plain; charset=utf-8", UserMetadata: map[string]string{"document-id": source.Payload.DocumentID}})
	if err != nil {
		return err
	}
	payload := events.NormalizedDocument{SourceID: source.Payload.SourceID, DocumentID: source.Payload.DocumentID, CanonicalURL: canonicalURL, Title: title, CleanTextObjectURI: "s3://" + a.bucket + "/" + cleanKey, ContentHash: source.Payload.ContentHash}
	normalized := events.NewEnvelope("document.normalized.v1", source.TenantID, source.CorrelationID, source.EventID, "stream-normalizer", "normalization", "normalized:"+source.Payload.DocumentID, source.OccurredAt, payload)
	if err := a.producer.PublishJSON(ctx, "document.normalized.v1", source.Payload.DocumentID, normalized); err != nil {
		return err
	}
	nlpPayload := map[string]any{"document_id": source.Payload.DocumentID, "source_id": source.Payload.SourceID, "clean_text_object_uri": payload.CleanTextObjectURI, "language_hint": payload.LanguageHint, "title": title, "canonical_url": canonicalURL}
	nlpRequest := events.NewEnvelope("document.nlp-requested.v1", source.TenantID, source.CorrelationID, normalized.EventID, "stream-normalizer", "nlp-request", "nlp:"+source.Payload.DocumentID+":default", source.OccurredAt, nlpPayload)
	if err := a.producer.PublishJSON(ctx, "document.nlp-requested.v1", source.Payload.DocumentID, nlpRequest); err != nil {
		return err
	}
	a.logger.Info("document normalized", "document_id", source.Payload.DocumentID, "correlation_id", source.CorrelationID, "characters", len(text))
	return nil
}

func parseObjectURI(uri string) (string, string, error) {
	if !strings.HasPrefix(uri, "s3://") {
		return "", "", errors.New("unsupported object URI")
	}
	parts := strings.SplitN(strings.TrimPrefix(uri, "s3://"), "/", 2)
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", "", errors.New("invalid object URI")
	}
	return parts[0], parts[1], nil
}

func extractHTML(body []byte) (string, string, error) {
	document, err := html.Parse(bytes.NewReader(body))
	if err != nil {
		return "", "", err
	}
	var title string
	var builder strings.Builder
	var walk func(*html.Node, bool)
	walk = func(node *html.Node, hidden bool) {
		if node.Type == html.ElementNode {
			tag := strings.ToLower(node.Data)
			hidden = hidden || tag == "script" || tag == "style" || tag == "noscript" || tag == "svg"
			if tag == "title" && node.FirstChild != nil {
				title = strings.TrimSpace(node.FirstChild.Data)
			}
		}
		if node.Type == html.TextNode && !hidden {
			value := strings.TrimSpace(node.Data)
			if value != "" {
				builder.WriteString(value)
				builder.WriteByte(' ')
			}
		}
		for child := node.FirstChild; child != nil; child = child.NextSibling {
			walk(child, hidden)
		}
	}
	walk(document, false)
	return title, strings.Join(strings.Fields(builder.String()), " "), nil
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
func envBool(key string, fallback bool) bool {
	value, err := strconv.ParseBool(os.Getenv(key))
	if err != nil {
		return fallback
	}
	return value
}
func fatal(logger *slog.Logger, action string, err error) {
	if err != nil {
		logger.Error(action, "error", err)
		os.Exit(1)
	}
}
