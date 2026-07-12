package main

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"
)

type alert struct {
	ID       string `json:"id"`
	TenantID string `json:"tenant_id"`
	Score    int    `json:"score"`
	Title    string `json:"title"`
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		tenant := r.Header.Get("X-Tenant-ID")
		if tenant == "" {
			http.Error(w, "missing tenant", http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		f, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "stream unsupported", 500)
			return
		}
		ticker := time.NewTicker(20 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-r.Context().Done():
				return
			case t := <-ticker.C:
				b, _ := json.Marshal(alert{ID: fmt.Sprintf("heartbeat-%d", t.Unix()), TenantID: tenant, Score: 0, Title: "heartbeat"})
				fmt.Fprintf(w, "event: heartbeat\ndata: %s\n\n", b)
				f.Flush()
			}
		}
	})
	logger.Info("realtime gateway listening", "address", ":8088")
	if err := http.ListenAndServe(":8088", mux); err != nil {
		logger.Error("server stopped", "error", err)
	}
}
