package main

import (
	"context"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/IBM/sarama"
	"github.com/Pepitodrop/signalchord/services/internal/kafkautil"
)

func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestBrokerIsolatesTenantsAndBoundsSlowConsumers(t *testing.T) {
	b := newBroker()
	a := b.subscribe("tenant-a")
	defer b.unsubscribe(a)
	other := b.subscribe("tenant-b")
	defer b.unsubscribe(other)
	if dropped := b.publish("tenant-a", []byte(`{"event_type":"alert.created.v1"}`)); dropped != 0 {
		t.Fatalf("unexpected drop: %d", dropped)
	}
	select {
	case <-a.ch:
	default:
		t.Fatal("tenant-a did not receive event")
	}
	select {
	case <-other.ch:
		t.Fatal("tenant-b received tenant-a event")
	default:
	}
	for i := 0; i < cap(a.ch); i++ {
		b.publish("tenant-a", []byte("x"))
	}
	if dropped := b.publish("tenant-a", []byte("overflow")); dropped != 1 {
		t.Fatalf("expected one bounded-buffer drop, got %d", dropped)
	}
}

func TestAuthorizedTenantUsesControlPlaneIntrospection(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer test-token" {
			t.Fatalf("unexpected authorization header")
		}
		if r.Header.Get("X-SignalChord-Internal-Token") != "internal-test" {
			t.Fatalf("unexpected internal token")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"organization_id":"tenant-a"}`))
	}))
	defer server.Close()
	t.Setenv("CONTROL_PLANE_URL", server.URL)
	t.Setenv("CONTROL_PLANE_INTERNAL_TOKEN", "internal-test")
	t.Setenv("SIGNALCHORD_ENV", "production")
	req := httptest.NewRequest(http.MethodGet, "/events", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	tenant, err := authorizedTenant(req)
	if err != nil || tenant != "tenant-a" {
		t.Fatalf("tenant=%q err=%v", tenant, err)
	}
}

func TestAuthorizedTenantRejectsUntrustedQueryInProduction(t *testing.T) {
	t.Setenv("SIGNALCHORD_ENV", "production")
	req := httptest.NewRequest(http.MethodGet, "/events?tenant_id=attacker", nil)
	if _, err := authorizedTenant(req); err == nil {
		t.Fatal("expected unauthorized query-only tenant")
	}
}

func TestRealtimeMessageHandler_MalformedJSONIsPermanent(t *testing.T) {
	handler := realtimeMessageHandler(discardLogger(), newBroker())
	message := &sarama.ConsumerMessage{Topic: "alert.created.v1", Value: []byte("{not json")}

	err := handler(context.Background(), message)

	if err == nil {
		t.Fatal("expected an error for malformed JSON")
	}
	if !kafkautil.IsPermanent(err) {
		t.Fatalf("expected a malformed payload to be classified permanent, got %v", err)
	}
}

func TestRealtimeMessageHandler_MissingTenantIDIsPermanent(t *testing.T) {
	handler := realtimeMessageHandler(discardLogger(), newBroker())
	message := &sarama.ConsumerMessage{
		Topic: "alert.created.v1",
		Value: []byte(`{"event_type":"alert.created.v1","payload":{}}`),
	}

	err := handler(context.Background(), message)

	if err == nil {
		t.Fatal("expected an error for a missing tenant_id")
	}
	if !kafkautil.IsPermanent(err) {
		t.Fatalf("expected a missing tenant_id to be classified permanent, got %v", err)
	}
}

func TestRealtimeMessageHandler_ValidEventSucceedsAndPublishesToSubscribers(t *testing.T) {
	stream := newBroker()
	sub := stream.subscribe("tenant-a")
	defer stream.unsubscribe(sub)
	handler := realtimeMessageHandler(discardLogger(), stream)
	message := &sarama.ConsumerMessage{
		Topic: "alert.created.v1",
		Value: []byte(`{"tenant_id":"tenant-a","event_type":"alert.created.v1"}`),
	}

	if err := handler(context.Background(), message); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if kafkautil.IsPermanent(nil) {
		t.Fatal("sanity check: nil must never be permanent")
	}
	select {
	case <-sub.ch:
	default:
		t.Fatal("expected the valid event to be published to the tenant's subscriber")
	}
}

func TestRealtimeDLQConfig_UsesStableOriginAndProvidedProducer(t *testing.T) {
	producer := &kafkautil.Producer{}

	cfg := realtimeDLQConfig(producer)

	if cfg.Origin != realtimeGatewayOrigin {
		t.Errorf("origin = %q, want %q", cfg.Origin, realtimeGatewayOrigin)
	}
	if cfg.Producer != producer {
		t.Error("expected the same producer instance to be wired through, not a copy")
	}
}
