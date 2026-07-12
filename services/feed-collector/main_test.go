package main

import (
	"testing"
	"time"
)

func TestSourceTimeUsesProvidedTime(t *testing.T) {
	v := time.Date(2026, 1, 2, 3, 4, 5, 0, time.FixedZone("x", 3600))
	got := sourceTime(&v)
	if got.Location() != time.UTC || got.Hour() != 2 {
		t.Fatalf("unexpected %v", got)
	}
}
