package streamnormalizer

import "testing"

func TestCanonicalizeURL(t *testing.T) {
	got, err := CanonicalizeURL("HTTPS://Example.COM/a?utm_source=x&b=2&a=1#x")
	if err != nil || got != "https://example.com/a?a=1&b=2" {
		t.Fatalf("%q %v", got, err)
	}
}
