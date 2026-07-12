package documentfetcher

import "testing"

func TestRejectLocalhost(t *testing.T) {
	if ValidateFetchURL("http://127.0.0.1/admin") == nil {
		t.Fatal("expected rejection")
	}
}
