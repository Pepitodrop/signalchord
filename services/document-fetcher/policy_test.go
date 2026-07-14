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

func TestRejectUnsupportedSchemesAndUserinfo(t *testing.T) {
	cases := []string{
		"file:///etc/passwd",
		"gopher://example.com",
		"https://user:password@example.com/feed",
	}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			if ValidateFetchURL(raw) == nil {
				t.Fatal("expected rejection")
			}
		})
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
