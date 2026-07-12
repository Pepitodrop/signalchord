require "rails_helper"

RSpec.describe "health", type: :request do
  it "reports the application version" do
    get "/healthz"
    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)).to include("status" => "ok", "version" => "1.0.0")
  end
end
