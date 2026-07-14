package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSafeHTTPClientRejectsRedirectToPrivateHost(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "http://localhost/metadata", http.StatusFound)
	}))
	defer server.Close()
	t.Setenv("FETCH_PRIVATE_HOST_ALLOWLIST", "127.0.0.1")

	response, err := safeHTTPClientWithTimeouts(2*time.Second, 2*time.Second).Get(server.URL)
	if response != nil {
		_ = response.Body.Close()
	}
	if err == nil || !strings.Contains(err.Error(), "private or local address denied") {
		t.Fatalf("expected redirect to private host to be denied, got response=%v err=%v", response, err)
	}
}

func TestSafeHTTPClientRejectsPrivateAddressAtDial(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("should not be reachable without allowlist"))
	}))
	defer server.Close()

	response, err := safeHTTPClientWithTimeouts(2*time.Second, 2*time.Second).Get(server.URL)
	if response != nil {
		_ = response.Body.Close()
	}
	if err == nil || !strings.Contains(err.Error(), "no permitted resolved address") {
		t.Fatalf("expected private address dial to be denied, got response=%v err=%v", response, err)
	}
}

func TestSafeHTTPClientTimesOutWaitingForHeaders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		time.Sleep(200 * time.Millisecond)
		_, _ = w.Write([]byte("late"))
	}))
	defer server.Close()
	t.Setenv("FETCH_PRIVATE_HOST_ALLOWLIST", "127.0.0.1")

	response, err := safeHTTPClientWithTimeouts(500*time.Millisecond, 25*time.Millisecond).Get(server.URL)
	if response != nil {
		_ = response.Body.Close()
	}
	if err == nil || !strings.Contains(err.Error(), "timeout awaiting response headers") {
		t.Fatalf("expected response-header timeout, got response=%v err=%v", response, err)
	}
}

func TestReadLimitedBodyRejectsOversizedResponse(t *testing.T) {
	_, err := readLimitedBody(strings.NewReader("abcdef"), 5)
	if err == nil || !strings.Contains(err.Error(), "document exceeds size limit") {
		t.Fatalf("expected size limit rejection, got %v", err)
	}
}
