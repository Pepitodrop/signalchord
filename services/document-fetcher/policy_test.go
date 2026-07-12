package documentfetcher

import (
	"os"
	"testing"
)

func TestRejectLocalhost(t *testing.T) {
	if ValidateFetchURL("http://127.0.0.1/admin") == nil {
		t.Fatal("expected rejection")
	}
}

func TestPrivateAllowlistIsExact(t *testing.T) {
	t.Setenv("FETCH_PRIVATE_HOST_ALLOWLIST", "sample-source")
	if !PrivateHostAllowed("sample-source") {
		t.Fatal("expected exact test host to be allowed")
	}
	if PrivateHostAllowed("sample-source.attacker.example") {
		t.Fatal("suffix host must not be allowed")
	}
	_ = os.Unsetenv("FETCH_PRIVATE_HOST_ALLOWLIST")
}
