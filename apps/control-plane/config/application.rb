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
    config.filter_parameters += %i[password token authorization midi_data]
  end
end
