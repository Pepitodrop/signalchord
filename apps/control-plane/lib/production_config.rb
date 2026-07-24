require "uri"

module ProductionConfig
  LOCAL_INTERNAL_TOKEN = "signalchord-local-internal"

  module_function

  def validate!(env = ENV)
    return unless production_environment?(env)

    errors = []
    errors << "FORCE_SSL must not be false" if env.fetch("FORCE_SSL", "true") == "false"
    errors.concat(validate_kafka(env))
    errors.concat(validate_database(env))
    errors.concat(validate_redis(env))
    errors.concat(validate_https_url(env, "OPENSEARCH_URL"))
    errors << "OPENSEARCH_VERIFY_CERTS must be true" unless truthy?(env["OPENSEARCH_VERIFY_CERTS"])
    errors << "OPENSEARCH_USERNAME is required" if env["OPENSEARCH_USERNAME"].to_s == ""
    errors << "OPENSEARCH_PASSWORD is required" if env["OPENSEARCH_PASSWORD"].to_s == ""
    errors.concat(validate_web_origins(env))
    errors.concat(validate_internal_token(env))
    errors.concat(validate_secret(env, "SECRET_KEY_BASE", 64))
    errors.concat(validate_secret(env, "NOTIFICATION_TOKEN_ENCRYPTION_KEY", 32))
    errors.concat(validate_beta_access_code(env))
    errors.concat(validate_smtp(env))
    raise "insecure production configuration: #{errors.join('; ')}" if errors.any?
  end

  def kafka_options(env = ENV)
    options = {
      seed_brokers: env.fetch("KAFKA_BROKERS", "localhost:29092").split(","),
      client_id: "signalchord-control-plane"
    }
    options[:ssl_ca_cert] = env["KAFKA_TLS_CA_PEM"] if truthy?(env["KAFKA_TLS_ENABLED"]) && env["KAFKA_TLS_CA_PEM"].to_s != ""
    if truthy?(env["KAFKA_SASL_ENABLED"])
      options[:sasl_plain_username] = env["KAFKA_SASL_USER"]
      options[:sasl_plain_password] = env["KAFKA_SASL_PASSWORD"]
    end
    options
  end

  def production_environment?(env)
    env["SIGNALCHORD_ENV"] == "production"
  end

  # Rails' Host-header allow-list (config.hosts). Empty array = no
  # restriction (Rails' own default), so deployments that haven't set
  # RAILS_ALLOWED_HOSTS yet keep today's behavior — this only tightens
  # things once it's actually configured.
  def allowed_hosts(env = ENV)
    env.fetch("RAILS_ALLOWED_HOSTS", "").split(",").map(&:strip).reject(&:empty?)
  end

  def validate_kafka(env)
    errors = []
    brokers = env.fetch("KAFKA_BROKERS", "").split(",").map(&:strip).reject(&:empty?)
    errors << "KAFKA_BROKERS is required" if brokers.empty?
    errors << "KAFKA_BROKERS cannot contain localhost or loopback addresses" if brokers.any? { |broker| local_address?(broker) }
    errors << "KAFKA_TLS_ENABLED must be true" unless truthy?(env["KAFKA_TLS_ENABLED"])
    errors << "KAFKA_SASL_ENABLED must be true" unless truthy?(env["KAFKA_SASL_ENABLED"])
    if truthy?(env["KAFKA_SASL_ENABLED"])
      errors << "KAFKA_SASL_USER is required" if env["KAFKA_SASL_USER"].to_s == ""
      errors << "KAFKA_SASL_PASSWORD is required" if env["KAFKA_SASL_PASSWORD"].to_s == ""
    end
    errors
  end

  def validate_database(env)
    database_url = env["DATABASE_URL"].to_s
    return ["DATABASE_URL is required"] if database_url == ""

    uri = URI.parse(database_url)
    errors = []
    errors << "DATABASE_URL cannot point at localhost" if local_address?(uri.host.to_s)
    errors << "DATABASE_URL must set sslmode=require or sslmode=verify-full" unless uri.query.to_s.match?(/(^|&)sslmode=(require|verify-full)(&|$)/)
    errors
  rescue URI::InvalidURIError
    ["DATABASE_URL is invalid"]
  end

  def validate_redis(env)
    env["REDIS_URL"].to_s.start_with?("rediss://") ? [] : ["REDIS_URL must use rediss://"]
  end

  def validate_https_url(env, key)
    value = env[key].to_s
    return ["#{key} is required"] if value == ""

    uri = URI.parse(value)
    errors = []
    errors << "#{key} must use https://" unless uri.scheme == "https"
    errors << "#{key} cannot point at localhost" if local_address?(uri.host.to_s)
    errors
  rescue URI::InvalidURIError
    ["#{key} is invalid"]
  end

  def validate_web_origins(env)
    origins = env.fetch("WEB_ORIGINS", "").split(",").map(&:strip).reject(&:empty?)
    return ["WEB_ORIGINS is required"] if origins.empty?

    origins.flat_map do |origin|
      uri = URI.parse(origin)
      errors = []
      errors << "WEB_ORIGINS must use https://" unless uri.scheme == "https"
      errors << "WEB_ORIGINS cannot contain localhost" if local_address?(uri.host.to_s)
      errors
    rescue URI::InvalidURIError
      ["WEB_ORIGINS contains an invalid origin"]
    end
  end

  def validate_internal_token(env)
    value = env["CONTROL_PLANE_INTERNAL_TOKEN"].to_s
    value.length >= 32 && value != LOCAL_INTERNAL_TOKEN ? [] : ["CONTROL_PLANE_INTERNAL_TOKEN must be a managed secret of at least 32 characters"]
  end

  def validate_secret(env, key, min_length)
    env[key].to_s.length >= min_length ? [] : ["#{key} must be a managed secret of at least #{min_length} characters"]
  end

  def validate_beta_access_code(env)
    value = env["BETA_ACCESS_CODE"].to_s
    return ["BETA_ACCESS_CODE is required"] if value == ""
    return ["BETA_ACCESS_CODE must not use the local development placeholder"] if value == "replace-me-with-a-real-shared-secret"
    return ["BETA_ACCESS_CODE must be at least 16 characters"] if value.length < 16

    []
  end

  def validate_smtp(env)
    host = env["SMTP_HOST"].to_s
    # local_address? assumes a non-empty host (matches every other call site
    # in this file, e.g. validate_https_url returns early the same way) —
    # "".split(":", 2) is [], not [""], so .first.delete_prefix would raise.
    return ["SMTP_HOST is required"] if host == ""

    local_address?(host) || host == "mailpit" ? ["SMTP_HOST cannot point at localhost or a local mail-catcher"] : []
  end

  def truthy?(value)
    value.to_s.strip.downcase == "true"
  end

  def local_address?(value)
    host = value.to_s.split(":", 2).first.delete_prefix("[").delete_suffix("]").downcase
    ["localhost", "127.0.0.1", "0.0.0.0", "::1", "::"].include?(host)
  end
end
