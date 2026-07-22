require_relative "../../lib/production_config"

RSpec.describe ProductionConfig do
  it "skips development defaults outside production" do
    expect { described_class.validate!("RAILS_ENV" => "production", "SIGNALCHORD_ENV" => "development") }.not_to raise_error
  end

  it "rejects local plaintext production defaults" do
    env = {
      "SIGNALCHORD_ENV" => "production",
      "FORCE_SSL" => "false",
      "KAFKA_BROKERS" => "localhost:29092",
      "KAFKA_TLS_ENABLED" => "false",
      "KAFKA_SASL_ENABLED" => "false",
      "DATABASE_URL" => "postgres://signalchord:secret@localhost:5432/signalchord",
      "REDIS_URL" => "redis://localhost:6379/0",
      "OPENSEARCH_URL" => "http://localhost:9200",
      "OPENSEARCH_VERIFY_CERTS" => "false",
      "WEB_ORIGINS" => "http://localhost:5173",
      "CONTROL_PLANE_INTERNAL_TOKEN" => "signalchord-local-internal",
      "SECRET_KEY_BASE" => "short",
      "NOTIFICATION_TOKEN_ENCRYPTION_KEY" => "short",
      "BETA_ACCESS_CODE" => "replace-me-with-a-real-shared-secret",
      "SMTP_HOST" => "mailpit"
    }

    expect { described_class.validate!(env) }.to raise_error(RuntimeError) do |error|
      expect(error.message).to include("KAFKA_TLS_ENABLED")
      expect(error.message).to include("DATABASE_URL")
      expect(error.message).to include("REDIS_URL")
      expect(error.message).to include("WEB_ORIGINS")
      expect(error.message).to include("CONTROL_PLANE_INTERNAL_TOKEN")
      expect(error.message).to include("BETA_ACCESS_CODE")
      expect(error.message).to include("SMTP_HOST")
    end
  end

  it "accepts encrypted managed production settings" do
    internal_token_key = "CONTROL_PLANE_" + "INTERNAL_TOKEN"
    env = {
      "SIGNALCHORD_ENV" => "production",
      "FORCE_SSL" => "true",
      "KAFKA_BROKERS" => "broker.kafka.svc:9093",
      "KAFKA_TLS_ENABLED" => "true",
      "KAFKA_SASL_ENABLED" => "true",
      "KAFKA_SASL_USER" => "runtime",
      "KAFKA_SASL_PASSWORD" => "managed-secret",
      "DATABASE_URL" => "postgres://signalchord:secret@postgres.database.svc:5432/signalchord?sslmode=verify-full",
      "REDIS_URL" => "rediss://redis.cache.svc:6379/0",
      "OPENSEARCH_URL" => "https://opensearch.search.svc:9200",
      "OPENSEARCH_VERIFY_CERTS" => "true",
      "OPENSEARCH_USERNAME" => "signalchord-search",
      "OPENSEARCH_PASSWORD" => "managed-secret",
      "WEB_ORIGINS" => "https://app.signalchord.example",
      "SECRET_KEY_BASE" => "a" * 64,
      "NOTIFICATION_TOKEN_ENCRYPTION_KEY" => "b" * 32,
      "BETA_ACCESS_CODE" => "c" * 24,
      "SMTP_HOST" => "smtp.postmarkapp.com"
    }
    env[internal_token_key] = "test-token-" * 4

    expect { described_class.validate!(env) }.not_to raise_error
  end

  describe "BETA_ACCESS_CODE and SMTP_HOST validation" do
    let(:base_env) do
      {
        "SIGNALCHORD_ENV" => "production",
        "FORCE_SSL" => "true",
        "KAFKA_BROKERS" => "broker.kafka.svc:9093",
        "KAFKA_TLS_ENABLED" => "true",
        "KAFKA_SASL_ENABLED" => "true",
        "KAFKA_SASL_USER" => "runtime",
        "KAFKA_SASL_PASSWORD" => "managed-secret",
        "DATABASE_URL" => "postgres://signalchord:secret@postgres.database.svc:5432/signalchord?sslmode=verify-full",
        "REDIS_URL" => "rediss://redis.cache.svc:6379/0",
        "OPENSEARCH_URL" => "https://opensearch.search.svc:9200",
        "OPENSEARCH_VERIFY_CERTS" => "true",
        "OPENSEARCH_USERNAME" => "signalchord-search",
        "OPENSEARCH_PASSWORD" => "managed-secret",
        "WEB_ORIGINS" => "https://app.signalchord.example",
        "SECRET_KEY_BASE" => "a" * 64,
        "NOTIFICATION_TOKEN_ENCRYPTION_KEY" => "b" * 32,
        "CONTROL_PLANE_INTERNAL_TOKEN" => "test-token-" * 4,
        "BETA_ACCESS_CODE" => "c" * 24,
        "SMTP_HOST" => "smtp.postmarkapp.com"
      }
    end

    it "rejects a missing BETA_ACCESS_CODE" do
      env = base_env.merge("BETA_ACCESS_CODE" => "")
      expect { described_class.validate!(env) }.to raise_error(/BETA_ACCESS_CODE is required/)
    end

    it "rejects the local development placeholder BETA_ACCESS_CODE" do
      env = base_env.merge("BETA_ACCESS_CODE" => "replace-me-with-a-real-shared-secret")
      expect { described_class.validate!(env) }.to raise_error(/local development placeholder/)
    end

    it "rejects a too-short BETA_ACCESS_CODE" do
      env = base_env.merge("BETA_ACCESS_CODE" => "short")
      expect { described_class.validate!(env) }.to raise_error(/at least 16 characters/)
    end

    it "rejects a missing SMTP_HOST" do
      env = base_env.merge("SMTP_HOST" => "")
      expect { described_class.validate!(env) }.to raise_error(/SMTP_HOST is required/)
    end

    it "rejects SMTP_HOST pointing at the local Mailpit dev container" do
      env = base_env.merge("SMTP_HOST" => "mailpit")
      expect { described_class.validate!(env) }.to raise_error(/local mail-catcher/)
    end

    it "accepts a real managed SMTP host and a real beta code" do
      expect { described_class.validate!(base_env) }.not_to raise_error
    end
  end
end
