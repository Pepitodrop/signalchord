package kafkautil

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
	"strings"

	"github.com/IBM/sarama"
)

func NewConfig() (*sarama.Config, error) {
	cfg := sarama.NewConfig()
	cfg.Version = sarama.V3_7_0_0
	if err := applySecurity(cfg, os.Getenv); err != nil {
		return nil, err
	}
	return cfg, nil
}

func applySecurity(cfg *sarama.Config, getenv func(string) string) error {
	if envBool(getenv("KAFKA_TLS_ENABLED")) {
		tlsConfig := &tls.Config{MinVersion: tls.VersionTLS12}
		if ca := strings.TrimSpace(getenv("KAFKA_TLS_CA_PEM")); ca != "" {
			pool := x509.NewCertPool()
			if !pool.AppendCertsFromPEM([]byte(ca)) {
				return fmt.Errorf("parse KAFKA_TLS_CA_PEM")
			}
			tlsConfig.RootCAs = pool
		}
		cfg.Net.TLS.Enable = true
		cfg.Net.TLS.Config = tlsConfig
	}
	if envBool(getenv("KAFKA_SASL_ENABLED")) {
		user := strings.TrimSpace(getenv("KAFKA_SASL_USER"))
		password := strings.TrimSpace(getenv("KAFKA_SASL_PASSWORD"))
		if user == "" || password == "" {
			return fmt.Errorf("KAFKA_SASL_USER and KAFKA_SASL_PASSWORD are required when KAFKA_SASL_ENABLED=true")
		}
		cfg.Net.SASL.Enable = true
		cfg.Net.SASL.User = user
		cfg.Net.SASL.Password = password
		switch strings.ToUpper(strings.TrimSpace(getenv("KAFKA_SASL_MECHANISM"))) {
		case "", "PLAIN":
			cfg.Net.SASL.Mechanism = sarama.SASLTypePlaintext
		default:
			return fmt.Errorf("unsupported KAFKA_SASL_MECHANISM")
		}
	}
	return nil
}

func envBool(value string) bool {
	return strings.EqualFold(strings.TrimSpace(value), "true")
}
