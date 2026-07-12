package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	documentfetcher "github.com/Pepitodrop/signalchord/services/document-fetcher"
	"github.com/Pepitodrop/signalchord/services/internal/events"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
	"github.com/IBM/sarama"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

const maxDocumentBytes = 10 << 20

type app struct {
	logger   *slog.Logger
	producer *kafkautil.Producer
	objects  *minio.Client
	bucket   string
	client   *http.Client
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
	bucket := env("MINIO_BUCKET", "raw-documents")
	exists, err := objects.BucketExists(ctx, bucket)
	fatal(logger, "check bucket", err)
	if !exists {
		fatal(logger, "create bucket", objects.MakeBucket(ctx, bucket, minio.MakeBucketOptions{}))
	}
	application := &app{logger: logger, producer: producer, objects: objects, bucket: bucket, client: safeHTTPClient()}
	err = kafkautil.Consume(ctx, brokers, "signalchord-document-fetcher-v1", []string{"source.document.discovered.v1"}, application.handle)
	if err != nil && !errors.Is(err, context.Canceled) {
		fatal(logger, "consume", err)
	}
}

func (a *app) handle(ctx context.Context, message *sarama.ConsumerMessage) error {
	var source events.Envelope[events.DocumentDiscovered]
	if err := json.Unmarshal(message.Value, &source); err != nil {
		return fmt.Errorf("decode discovered event: %w", err)
	}
	if err := documentfetcher.ValidateFetchURL(source.Payload.URL); err != nil {
		return fmt.Errorf("fetch policy rejected URL: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, source.Payload.URL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", env("SIGNALCHORD_USER_AGENT", "SignalChord/0.1 (+https://signalchord.example/source-policy)"))
	response, err := a.client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("unexpected HTTP status %d", response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxDocumentBytes+1))
	if err != nil {
		return err
	}
	if len(body) > maxDocumentBytes {
		return errors.New("document exceeds size limit")
	}
	digest := sha256.Sum256(body)
	hash := hex.EncodeToString(digest[:])
	documentID := "doc:" + hash
	key := fmt.Sprintf("raw/%s/%s/%s", source.TenantID, source.Payload.SourceID, hash)
	mediaType := response.Header.Get("Content-Type")
	_, err = a.objects.PutObject(ctx, a.bucket, key, bytes.NewReader(body), int64(len(body)), minio.PutObjectOptions{ContentType: mediaType, UserMetadata: map[string]string{"source-url": response.Request.URL.String(), "content-sha256": hash}})
	if err != nil {
		return fmt.Errorf("store raw document: %w", err)
	}
	payload := events.DocumentFetched{DocumentID: documentID, SourceID: source.Payload.SourceID, FinalURL: response.Request.URL.String(), ContentHash: hash, ObjectURI: "s3://" + a.bucket + "/" + key, MediaType: mediaType, Charset: "", HTTPStatus: response.StatusCode, HTTPHeaders: safeHeaders(response.Header)}
	envelope := events.NewEnvelope("source.document.fetched.v1", source.TenantID, source.CorrelationID, source.EventID, "document-fetcher", "fetch", "fetch:"+documentID, source.OccurredAt, payload)
	if err := a.producer.PublishJSON(ctx, "source.document.fetched.v1", documentID, envelope); err != nil {
		return err
	}
	a.logger.Info("document fetched", "document_id", documentID, "correlation_id", source.CorrelationID, "bytes", len(body))
	return nil
}

func safeHTTPClient() *http.Client {
	dialer := &net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}
	transport := &http.Transport{Proxy: http.ProxyFromEnvironment, MaxIdleConns: 50, IdleConnTimeout: 60 * time.Second, ResponseHeaderTimeout: 15 * time.Second}
	transport.DialContext = func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil {
			return nil, err
		}
		ips, err := net.DefaultResolver.LookupIP(ctx, "ip", host)
		if err != nil {
			return nil, err
		}
		for _, ip := range ips {
			if !documentfetcher.IsDeniedIP(ip) {
				return dialer.DialContext(ctx, network, net.JoinHostPort(ip.String(), port))
			}
		}
		return nil, errors.New("no permitted resolved address")
	}
	return &http.Client{Transport: transport, Timeout: 30 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 {
			return errors.New("redirect limit exceeded")
		}
		return documentfetcher.ValidateFetchURL(req.URL.String())
	}}
}

func safeHeaders(headers http.Header) map[string]string {
	allowed := map[string]bool{"Content-Type": true, "Content-Length": true, "ETag": true, "Last-Modified": true, "Cache-Control": true}
	result := map[string]string{}
	for key := range allowed {
		if value := headers.Get(key); value != "" {
			result[key] = value
		}
	}
	return result
}

func env(key, fallback string) string { if value := os.Getenv(key); value != "" { return value }; return fallback }
func envBool(key string, fallback bool) bool { value, err := strconv.ParseBool(os.Getenv(key)); if err != nil { return fallback }; return value }
func fatal(logger *slog.Logger, action string, err error) { if err != nil { logger.Error(action, "error", err); os.Exit(1) } }
var _ = url.URL{}
