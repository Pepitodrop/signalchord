package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

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
