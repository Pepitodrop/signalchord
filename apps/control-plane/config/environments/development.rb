require "active_support/core_ext/integer/time"
Rails.application.configure do
  config.enable_reloading = true
  config.eager_load = false
  config.consider_all_requests_local = true
  config.server_timing = true
  config.active_storage.service = :local
  config.active_support.deprecation = :log
  config.active_record.migration_error = :page_load
  config.hosts.clear

  config.action_mailer.delivery_method = :smtp
  config.action_mailer.smtp_settings = {
    address: ENV.fetch("SMTP_HOST", "mailpit"),
    port: ENV.fetch("SMTP_PORT", 1025).to_i,
    user_name: ENV["SMTP_USERNAME"].presence,
    password: ENV["SMTP_PASSWORD"].presence,
    authentication: ENV["SMTP_AUTHENTICATION"].presence || "plain",
    enable_starttls_auto: ENV.fetch("SMTP_STARTTLS", "false") == "true",
    open_timeout: ENV.fetch("SMTP_OPEN_TIMEOUT", 5).to_i,
    read_timeout: ENV.fetch("SMTP_READ_TIMEOUT", 5).to_i
  }
  config.action_mailer.raise_delivery_errors = true
  config.action_mailer.perform_caching = false
end
