package main

import "testing"

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
