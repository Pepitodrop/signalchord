require "active_support/core_ext/integer/time"
Rails.application.configure do
  config.enable_reloading = false
  config.eager_load = true
  config.consider_all_requests_local = false
  config.force_ssl = ENV.fetch("FORCE_SSL", "true") == "true"
  config.log_level = ENV.fetch("RAILS_LOG_LEVEL", "info")
  config.log_tags = [:request_id]
  config.active_support.report_deprecations = false
  config.active_record.dump_schema_after_migration = false

  # Guarded on SMTP_HOST being present (rather than ENV.fetch with no
  # default) so processes that boot this same Rails app but never send mail
  # (bin/outbox-publisher, any future worker) don't fail to boot entirely
  # just because they weren't given mail-provider credentials.
  if ENV["SMTP_HOST"].present?
    config.action_mailer.delivery_method = :smtp
    config.action_mailer.smtp_settings = {
      address: ENV.fetch("SMTP_HOST"),
      port: ENV.fetch("SMTP_PORT", 587).to_i,
      user_name: ENV["SMTP_USERNAME"].presence,
      password: ENV["SMTP_PASSWORD"].presence,
      authentication: ENV["SMTP_AUTHENTICATION"].presence || "plain",
      enable_starttls_auto: ENV.fetch("SMTP_STARTTLS", "true") == "true",
      open_timeout: ENV.fetch("SMTP_OPEN_TIMEOUT", 5).to_i,
      read_timeout: ENV.fetch("SMTP_READ_TIMEOUT", 5).to_i
    }
  end
  config.action_mailer.raise_delivery_errors = true
  config.action_mailer.perform_caching = false
end
