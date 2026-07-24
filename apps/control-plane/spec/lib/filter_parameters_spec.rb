require "rails_helper"

RSpec.describe "config.filter_parameters" do
  it "filters midi_base64 (the real wire param key), not the nonexistent midi_data" do
    filter = ActiveSupport::ParameterFilter.new(Rails.application.config.filter_parameters)
    filtered = filter.filter({ "midi_base64" => "up-to-128kb-of-midi-binary" })

    expect(filtered["midi_base64"]).to eq(ActiveSupport::ParameterFilter::FILTERED)
  end
end
