require "rails_helper"

RSpec.describe "sources", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:owner) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user: owner, role: "owner") }
  let!(:token) { ApiToken.issue!(organization:, user: owner, name: "test", scopes: Membership.scopes_for("owner")).last }
  let(:owner_headers) { { "Authorization" => "Bearer #{token}" } }

  def approved_metadata
    {
      "owner" => "news-ops",
      "legal_basis" => "contract",
      "permitted_uses" => ["analysis", "alerts"],
      "attribution" => "Source",
      "terms_status" => "approved",
      "geography" => ["US"],
      "retention_days" => 30,
      "deletion_obligations" => ["delete_raw_and_derived_on_request"]
    }
  end

  let!(:own_record) do
    organization.sources.create!(name: "Alpha feed", endpoint: "https://alpha.example/feed", adapter: "rss",
                                  rights_status: "approved", raw_retention_days: 30, policy_metadata: approved_metadata, enabled: true)
  end

  let!(:other_organization) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:other_record) do
    other_organization.sources.create!(name: "Beta feed", endpoint: "https://beta.example/feed", adapter: "rss",
                                        rights_status: "approved", raw_retention_days: 30, policy_metadata: approved_metadata, enabled: true)
  end

  let(:index_path) { "/api/v1/sources" }
  let(:show_path) { ->(id) { "/api/v1/sources/#{id}" } }
  let(:update_path) { ->(id) { "/api/v1/sources/#{id}" } }
  let(:update_params) { { source: { name: "hijacked" } } }

  include_examples "a tenant-isolated resource"

  it "requires api:write scope to create" do
    viewer = User.create!(email: "viewer@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: viewer, role: "viewer")
    _record, viewer_token = ApiToken.issue!(organization:, user: viewer, name: "test", scopes: Membership.scopes_for("viewer"))

    post "/api/v1/sources",
         params: { source: { name: "Blocked", endpoint: "https://x.example/feed", adapter: "rss", rights_status: "pending" } },
         headers: { "Authorization" => "Bearer #{viewer_token}" }

    expect(response).to have_http_status(:forbidden)
  end
end
