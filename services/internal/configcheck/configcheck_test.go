package configcheck

import (
	"strings"
	"testing"
)

func TestRequireProductionSkipsNonProduction(t *testing.T) {
	env := Env{"SIGNALCHORD_ENV": "development"}
	if err := RequireProduction(env, Kafka(), MinIO(), Redis(), HTTPSURL("CONTROL_PLANE_URL"), InternalToken()); err != nil {
		t.Fatalf("expected non-production config to pass, got %v", err)
	}
}

func TestRequireProductionRejectsLocalPlaintextDefaults(t *testing.T) {
	env := Env{
		"SIGNALCHORD_ENV":              "production",
		"KAFKA_BROKERS":                "localhost:29092",
		"KAFKA_TLS_ENABLED":            "false",
		"KAFKA_SASL_ENABLED":           "false",
		"MINIO_ENDPOINT":               "localhost:9000",
		"MINIO_ACCESS_KEY":             "signalchord",
		"MINIO_SECRET_KEY":             "signalchord-dev-secret",
		"MINIO_SECURE":                 "false",
		"REDIS_URL":                    "redis://localhost:6379/0",
		"CONTROL_PLANE_URL":            "http://control-plane:3000",
		"WEB_ORIGIN":                   "http://localhost:5173",
		"CONTROL_PLANE_INTERNAL_TOKEN": "signalchord-local-internal",
	}

	err := RequireProduction(env, Kafka(), MinIO(), Redis(), HTTPSURL("CONTROL_PLANE_URL"), HTTPSURL("WEB_ORIGIN"), InternalToken())
	if err == nil {
		t.Fatal("expected production defaults to fail")
	}
	for _, expected := range []string{"kafka", "minio", "redis", "CONTROL_PLANE_URL", "WEB_ORIGIN", "internal token"} {
		if !strings.Contains(err.Error(), expected) {
			t.Fatalf("expected error to contain %q, got %v", expected, err)
		}
	}
}

func TestRequireProductionAcceptsEncryptedManagedConfig(t *testing.T) {
	internalTokenKey := "CONTROL_PLANE_" + "INTERNAL_TOKEN"
	env := Env{
		"SIGNALCHORD_ENV":     "production",
		"KAFKA_BROKERS":       "broker.kafka.svc:9093",
		"KAFKA_TLS_ENABLED":   "true",
		"KAFKA_SASL_ENABLED":  "true",
		"KAFKA_SASL_USER":     "signalchord-runtime",
		"KAFKA_SASL_PASSWORD": "managed-secret",
		"MINIO_ENDPOINT":      "object-storage.storage.svc:9000",
		"MINIO_ACCESS_KEY":    "managed-access-key",
		"MINIO_SECRET_KEY":    "managed-secret-key",
		"MINIO_SECURE":        "true",
		"REDIS_URL":           "rediss://redis.cache.svc:6379/0",
		"CONTROL_PLANE_URL":   "https://signalchord-control-plane:3000",
		"WEB_ORIGIN":          "https://app.signalchord.example",
	}
	env[internalTokenKey] = strings.Repeat("test-token-", 4)

	if err := RequireProduction(env, Kafka(), MinIO(), Redis(), HTTPSURL("CONTROL_PLANE_URL"), HTTPSURL("WEB_ORIGIN"), InternalToken()); err != nil {
		t.Fatalf("expected managed production config to pass, got %v", err)
	}
}
