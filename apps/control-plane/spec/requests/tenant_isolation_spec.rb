require "rails_helper"

RSpec.describe "tenant isolation", type: :request do
  let!(:alpha) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:beta) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:token) do
    record, plaintext = ApiToken.issue!(organization: alpha, name: "test", scopes: ["*"])
    plaintext
  end
  let!(:alpha_source) { alpha.sources.create!(name: "Alpha feed", endpoint: "https://alpha.example/feed", adapter: "rss", rights_status: "approved") }
  let!(:beta_source) { beta.sources.create!(name: "Beta feed", endpoint: "https://beta.example/feed", adapter: "rss", rights_status: "approved") }

  it "never returns another tenant's source" do
    get "/api/v1/sources", headers: { "Authorization" => "Bearer #{token}" }
    ids = JSON.parse(response.body).map { |source| source.fetch("id") }
    expect(ids).to include(alpha_source.id)
    expect(ids).not_to include(beta_source.id)
  end
end
