package main

import (
	"strings"
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

func TestLoadSourcePolicyRequiresProductionPolicy(t *testing.T) {
	t.Setenv("SIGNALCHORD_ENV", "production")
	t.Setenv("SOURCE_POLICY_JSON", "")

	_, err := loadSourcePolicy("source-1")
	if err == nil || !strings.Contains(err.Error(), "SOURCE_POLICY_JSON is required") {
		t.Fatalf("expected production policy error, got %v", err)
	}
}

func TestLoadSourcePolicyRejectsUnapprovedSource(t *testing.T) {
	t.Setenv("SOURCE_POLICY_JSON", `{"source_id":"source-1","rights_status":"pending_review","owner":"news-ops","legal_basis":"contract","permitted_uses":["analysis"],"attribution":"Required","terms_status":"approved","geography":"US","retention_days":30,"deletion_obligations":"delete on request"}`)

	_, err := loadSourcePolicy("source-1")
	if err == nil || !strings.Contains(err.Error(), "rights_status must be approved") {
		t.Fatalf("expected rights error, got %v", err)
	}
}

func TestLoadSourcePolicyRejectsMismatchedSourceID(t *testing.T) {
	t.Setenv("SOURCE_POLICY_JSON", `{"source_id":"source-2","rights_status":"approved","owner":"news-ops","legal_basis":"contract","permitted_uses":["analysis"],"attribution":"Required","terms_status":"approved","geography":"US","retention_days":30,"deletion_obligations":"delete on request"}`)

	_, err := loadSourcePolicy("source-1")
	if err == nil || !strings.Contains(err.Error(), "does not match") {
		t.Fatalf("expected source mismatch error, got %v", err)
	}
}

func TestSourcePolicyAttributesIncludeRetentionAndOwner(t *testing.T) {
	t.Setenv("SOURCE_POLICY_JSON", `{"source_id":"source-1","rights_status":"approved","owner":"news-ops","legal_basis":"contract","permitted_uses":["analysis","alerts"],"attribution":"Required","terms_status":"approved","geography":"US","retention_days":30,"deletion_obligations":"delete on request"}`)
	policy, err := loadSourcePolicy("source-1")
	if err != nil {
		t.Fatal(err)
	}

	attributes := sourcePolicyAttributes(policy)
	if attributes["source_policy.owner"] != "news-ops" {
		t.Fatalf("missing owner attribute: %#v", attributes)
	}
	if attributes["source_policy.retention_days"] != "30" {
		t.Fatalf("missing retention attribute: %#v", attributes)
	}
	if attributes["source_policy.permitted_uses"] != "analysis,alerts" {
		t.Fatalf("missing uses attribute: %#v", attributes)
	}
}
