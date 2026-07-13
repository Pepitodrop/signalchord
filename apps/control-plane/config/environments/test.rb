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
end
