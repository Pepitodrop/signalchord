package kafkautil

import (
	"testing"

	"github.com/IBM/sarama"
)

func TestApplySecurityEnablesTLSAndSASLPlain(t *testing.T) {
	cfg := sarama.NewConfig()
	values := map[string]string{
		"KAFKA_TLS_ENABLED":   "true",
		"KAFKA_SASL_ENABLED":  "true",
		"KAFKA_SASL_USER":     "runtime",
		"KAFKA_SASL_PASSWORD": "secret",
	}
	err := applySecurity(cfg, func(key string) string { return values[key] })
	if err != nil {
		t.Fatalf("apply security: %v", err)
	}
	if !cfg.Net.TLS.Enable {
		t.Fatal("expected TLS to be enabled")
	}
	if !cfg.Net.SASL.Enable || cfg.Net.SASL.User != "runtime" || cfg.Net.SASL.Mechanism != sarama.SASLTypePlaintext {
		t.Fatalf("unexpected SASL config: %+v", cfg.Net.SASL)
	}
}

func TestApplySecurityRejectsMissingSASLCredentials(t *testing.T) {
	cfg := sarama.NewConfig()
	values := map[string]string{"KAFKA_SASL_ENABLED": "true"}
	err := applySecurity(cfg, func(key string) string { return values[key] })
	if err == nil {
		t.Fatal("expected missing credentials to fail")
	}
}
