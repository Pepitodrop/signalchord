require_relative "boot"
require "rails/all"

Bundler.require(*Rails.groups)

module SignalChordControlPlane
  class Application < Rails::Application
    config.load_defaults 8.0
    config.api_only = true
    config.time_zone = "UTC"
    config.active_record.default_timezone = :utc
    config.active_job.queue_adapter = :sidekiq
    config.generators.system_tests = nil
    # midi_base64 is the actual wire param key (see PoliciesController#upload_velato) —
    # up to 128KB of MIDI binary that would otherwise never be filtered from
    # Rails' parameter logs in production.
    config.filter_parameters += %i[password token authorization midi_base64 beta_access_code]

    # config.api_only strips ActionDispatch::Cookies from the default
    # middleware stack (API-only apps normally use bearer tokens, not
    # cookies). The closed-beta web session needs a real httpOnly cookie, so
    # add it back explicitly — controllers additionally need
    # `include ActionController::Cookies` (see CookieSession concern).
    config.middleware.use ActionDispatch::Cookies
  end
end
