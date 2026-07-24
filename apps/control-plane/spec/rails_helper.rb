ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
abort("The Rails environment is running in production mode!") if Rails.env.production?
require "rspec/rails"
require_relative "spec_helper"

Dir[Rails.root.join("spec/support/**/*.rb")].sort.each { |file| require file }

begin
  ActiveRecord::Migration.maintain_test_schema!
rescue ActiveRecord::PendingMigrationError => error
  abort error.to_s.strip
end

RSpec.configure do |config|
  config.fixture_paths = [Rails.root.join("spec/fixtures")]
  config.use_transactional_fixtures = true
  config.infer_spec_type_from_file_location!
  config.filter_rails_from_backtrace!
  config.include ActiveSupport::Testing::TimeHelpers
  config.include ActiveJob::TestHelper

  # ActiveJob's :test adapter (config/environments/test.rb) accumulates
  # enqueued_jobs across examples unless explicitly cleared — the per-example
  # transactional rollback only resets the database, not this in-memory queue.
  config.after { clear_enqueued_jobs }
end
