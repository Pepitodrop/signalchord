require "active_support/core_ext/integer/time"
Rails.application.configure do
  config.enable_reloading = false
  config.eager_load = ENV["CI"].present?
  config.public_file_server.enabled = true
  config.consider_all_requests_local = true
  config.action_dispatch.show_exceptions = :rescuable
  config.active_storage.service = :test
  config.active_support.deprecation = :stderr
  config.action_controller.allow_forgery_protection = false

  # Without this, ActionMailer falls back to its :smtp default in every
  # environment that doesn't explicitly set delivery_method — including test,
  # since this app's development.rb/production.rb blocks only run under
  # their own Rails.env. That meant CI attempted a real SMTP connection,
  # which failed and was silently caught by the app's own rescue (deliberate,
  # for production resilience), showing up as "0 deliveries" instead of an
  # error.
  config.action_mailer.delivery_method = :test
  config.action_mailer.perform_deliveries = true

  # application.rb sets queue_adapter = :sidekiq for every environment; override
  # to :test here so specs that enqueue jobs (AlertEmailNotificationJob) don't
  # require a real Redis connection, matching the delivery_method override above.
  config.active_job.queue_adapter = :test
end
