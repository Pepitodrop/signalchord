package configcheck

import (
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"
)

const (
	localInternalToken = "signalchord-local-internal"
	devMinioAccessKey  = "signalchord"
	devMinioSecretKey  = "signalchord-dev-secret"
)

type Requirement struct {
	Name  string
	Check func(Env) error
}

type Env map[string]string

func CurrentEnv() Env {
	env := Env{}
	for _, item := range os.Environ() {
		key, value, ok := strings.Cut(item, "=")
		if ok {
			env[key] = value
		}
	}
	return env
}

func RequireProduction(env Env, requirements ...Requirement) error {
	if strings.ToLower(env.Value("SIGNALCHORD_ENV")) != "production" {
		return nil
	}
	var errs []error
	for _, requirement := range requirements {
		if err := requirement.Check(env); err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", requirement.Name, err))
		}
	}
	return errors.Join(errs...)
}

func Kafka() Requirement {
	return Requirement{Name: "kafka", Check: func(env Env) error {
		brokers := splitCSV(env.Value("KAFKA_BROKERS"))
		if len(brokers) == 0 {
			return errors.New("KAFKA_BROKERS is required")
		}
		var errs []error
		for _, broker := range brokers {
			if isLocalAddress(broker) {
				errs = append(errs, fmt.Errorf("broker %q is local-only", broker))
			}
		}
		if !env.Bool("KAFKA_TLS_ENABLED") {
			errs = append(errs, errors.New("KAFKA_TLS_ENABLED must be true"))
		}
		if !env.Bool("KAFKA_SASL_ENABLED") {
			errs = append(errs, errors.New("KAFKA_SASL_ENABLED must be true"))
		}
		if env.Bool("KAFKA_SASL_ENABLED") {
			if env.Value("KAFKA_SASL_USER") == "" {
				errs = append(errs, errors.New("KAFKA_SASL_USER is required"))
			}
			if env.Value("KAFKA_SASL_PASSWORD") == "" {
				errs = append(errs, errors.New("KAFKA_SASL_PASSWORD is required"))
			}
		}
		return errors.Join(errs...)
	}}
}

func MinIO() Requirement {
	return Requirement{Name: "minio", Check: func(env Env) error {
		var errs []error
		if env.Value("MINIO_ENDPOINT") == "" {
			errs = append(errs, errors.New("MINIO_ENDPOINT is required"))
		}
		if isLocalAddress(env.Value("MINIO_ENDPOINT")) {
			errs = append(errs, errors.New("MINIO_ENDPOINT cannot point at localhost"))
		}
		if !env.Bool("MINIO_SECURE") {
			errs = append(errs, errors.New("MINIO_SECURE must be true"))
		}
		if value := env.Value("MINIO_ACCESS_KEY"); value == "" || value == devMinioAccessKey {
			errs = append(errs, errors.New("MINIO_ACCESS_KEY must be a managed secret"))
		}
		if value := env.Value("MINIO_SECRET_KEY"); value == "" || value == devMinioSecretKey {
			errs = append(errs, errors.New("MINIO_SECRET_KEY must be a managed secret"))
		}
		return errors.Join(errs...)
	}}
}

func Redis() Requirement {
	return Requirement{Name: "redis", Check: func(env Env) error {
		value := env.Value("REDIS_URL")
		if value == "" {
			return errors.New("REDIS_URL is required")
		}
		if !strings.HasPrefix(value, "rediss://") {
			return errors.New("REDIS_URL must use rediss://")
		}
		return nil
	}}
}

func HTTPSURL(key string) Requirement {
	return Requirement{Name: key, Check: func(env Env) error {
		value := env.Value(key)
		if value == "" {
			return fmt.Errorf("%s is required", key)
		}
		parsed, err := url.Parse(value)
		if err != nil {
			return err
		}
		if parsed.Scheme != "https" {
			return fmt.Errorf("%s must use https://", key)
		}
		if isLocalAddress(parsed.Host) {
			return fmt.Errorf("%s cannot point at localhost", key)
		}
		return nil
	}}
}

func InternalToken() Requirement {
	return Requirement{Name: "internal token", Check: func(env Env) error {
		value := env.Value("CONTROL_PLANE_INTERNAL_TOKEN")
		if value == "" || value == localInternalToken || len(value) < 32 {
			return errors.New("CONTROL_PLANE_INTERNAL_TOKEN must be a managed secret of at least 32 characters")
		}
		return nil
	}}
}

func (e Env) Value(key string) string {
	return strings.TrimSpace(e[key])
}

func (e Env) Bool(key string) bool {
	return strings.EqualFold(e.Value(key), "true")
}

func splitCSV(value string) []string {
	var result []string
	for _, part := range strings.Split(value, ",") {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}

func isLocalAddress(value string) bool {
	if value == "" {
		return false
	}
	host := value
	if strings.Contains(value, "://") {
		if parsed, err := url.Parse(value); err == nil {
			host = parsed.Host
		}
	}
	if splitHost, _, err := net.SplitHostPort(host); err == nil {
		host = splitHost
	}
	host = strings.Trim(strings.ToLower(host), "[]")
	if host == "localhost" || host == "0.0.0.0" || host == "::" || host == "::1" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && (ip.IsLoopback() || ip.IsUnspecified())
}
