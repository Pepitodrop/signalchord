package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/IBM/sarama"
	"github.com/Pepitodrop/signalchord/services/internal/configcheck"
	"github.com/Pepitodrop/signalchord/services/internal/events"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
)

type subscription struct {
	id     uint64
	tenant string
	ch     chan []byte
}

type broker struct {
	mu          sync.RWMutex
	nextID      uint64
	subscribers map[string]map[uint64]chan []byte
}

type tokenIntrospection struct {
	OrganizationID string `json:"organization_id"`
}

func newBroker() *broker {
	return &broker{subscribers: make(map[string]map[uint64]chan []byte)}
}

func (b *broker) subscribe(tenant string) subscription {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.nextID++
	if b.subscribers[tenant] == nil {
		b.subscribers[tenant] = make(map[uint64]chan []byte)
	}
	ch := make(chan []byte, 64)
	b.subscribers[tenant][b.nextID] = ch
	return subscription{id: b.nextID, tenant: tenant, ch: ch}
}

func (b *broker) unsubscribe(sub subscription) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if tenants := b.subscribers[sub.tenant]; tenants != nil {
		delete(tenants, sub.id)
		if len(tenants) == 0 {
			delete(b.subscribers, sub.tenant)
		}
	}
}

func (b *broker) publish(tenant string, payload []byte) int {
	b.mu.RLock()
	defer b.mu.RUnlock()
	dropped := 0
	for _, ch := range b.subscribers[tenant] {
		copyPayload := append([]byte(nil), payload...)
		select {
		case ch <- copyPayload:
		default:
			dropped++
		}
	}
	return dropped
}

func main() {
	signalCtx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	ctx, cancel := context.WithCancel(signalCtx)
	defer cancel()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := configcheck.RequireProduction(configcheck.CurrentEnv(), configcheck.Kafka(), configcheck.HTTPSURL("CONTROL_PLANE_URL"), configcheck.HTTPSURL("WEB_ORIGIN"), configcheck.InternalToken()); err != nil {
		logger.Error("validate production config", "error", err)
		os.Exit(1)
	}
	stream := newBroker()
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:29092"), ",")

	go func() {
		err := kafkautil.Consume(ctx, brokers, "signalchord-realtime-gateway-v1", []string{"alert.created.v1", "graph.mutation-completed.v1"}, func(_ context.Context, message *sarama.ConsumerMessage) error {
			var envelope events.Envelope[json.RawMessage]
			if err := json.Unmarshal(message.Value, &envelope); err != nil {
				return fmt.Errorf("decode realtime event: %w", err)
			}
			if envelope.TenantID == "" {
				return errors.New("realtime event missing tenant_id")
			}
			if dropped := stream.publish(envelope.TenantID, message.Value); dropped > 0 {
				logger.Warn("realtime messages dropped for slow subscribers", "tenant_id", envelope.TenantID, "dropped", dropped, "event_type", envelope.EventType)
			}
			return nil
		})
		if err != nil && !errors.Is(err, context.Canceled) {
			logger.Error("Kafka consumer stopped", "error", err)
			cancel()
		}
	}()

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/events", sseHandler(logger, stream))
	server := &http.Server{Addr: ":8088", Handler: securityHeaders(mux), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 75 * time.Second}
	go func() {
		logger.Info("realtime gateway listening", "address", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("HTTP server stopped", "error", err)
			cancel()
		}
	}()
	<-ctx.Done()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
	}
}

func sseHandler(logger *slog.Logger, stream *broker) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		setCORS(w, r)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		tenant, err := authorizedTenant(r)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "stream unsupported", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache, no-transform")
		w.Header().Set("Connection", "keep-alive")
		sub := stream.subscribe(tenant)
		defer stream.unsubscribe(sub)
		logger.Info("realtime subscriber connected", "tenant_id", tenant, "subscriber_id", sub.id)
		heartbeat := time.NewTicker(20 * time.Second)
		defer heartbeat.Stop()
		fmt.Fprint(w, "retry: 3000\n\n")
		flusher.Flush()
		for {
			select {
			case <-r.Context().Done():
				return
			case payload := <-sub.ch:
				fmt.Fprintf(w, "event: alert\ndata: %s\n\n", payload)
				flusher.Flush()
			case now := <-heartbeat.C:
				fmt.Fprintf(w, "event: heartbeat\ndata: {\"at\":%q}\n\n", now.UTC().Format(time.RFC3339))
				flusher.Flush()
			}
		}
	}
}

func authorizedTenant(r *http.Request) (string, error) {
	authorization := r.Header.Get("Authorization")
	if authorization == "" && env("SIGNALCHORD_ENV", "development") == "development" {
		if tenant := r.URL.Query().Get("tenant_id"); tenant != "" {
			return tenant, nil
		}
	}
	if !strings.HasPrefix(authorization, "Bearer ") {
		return "", errors.New("missing bearer token")
	}
	base := strings.TrimRight(env("CONTROL_PLANE_URL", "http://control-plane:3000"), "/")
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, base+"/internal/v1/token", nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", authorization)
	req.Header.Set("X-SignalChord-Internal-Token", env("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal"))
	client := &http.Client{Timeout: 5 * time.Second}
	response, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return "", fmt.Errorf("introspection returned %d", response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, 64<<10))
	if err != nil {
		return "", err
	}
	var result tokenIntrospection
	if err := json.Unmarshal(body, &result); err != nil {
		return "", err
	}
	if result.OrganizationID == "" {
		return "", errors.New("introspection missing organization")
	}
	return result.OrganizationID, nil
}

func setCORS(w http.ResponseWriter, r *http.Request) {
	allowed := env("WEB_ORIGIN", "http://localhost:5173")
	if r.Header.Get("Origin") == allowed {
		w.Header().Set("Access-Control-Allow-Origin", allowed)
		w.Header().Set("Vary", "Origin")
	}
	w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		next.ServeHTTP(w, r)
	})
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
