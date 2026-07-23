require "rails_helper"

RSpec.describe "investigations", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:owner) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user: owner, role: "owner") }
  let!(:token) { ApiToken.issue!(organization:, user: owner, name: "test", scopes: Membership.scopes_for("owner")).last }
  let(:owner_headers) { { "Authorization" => "Bearer #{token}" } }
  let!(:own_record) { organization.investigations.create!(name: "Alpha investigation") }

  let!(:other_organization) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:other_record) { other_organization.investigations.create!(name: "Beta investigation") }

  let(:index_path) { "/api/v1/investigations" }
  let(:show_path) { ->(id) { "/api/v1/investigations/#{id}" } }
  let(:update_path) { ->(id) { "/api/v1/investigations/#{id}" } }
  let(:update_params) { { investigation: { name: "hijacked" } } }

  include_examples "a tenant-isolated resource"

  it "creates an investigation scoped to the caller's own organization" do
    post "/api/v1/investigations", params: { investigation: { name: "New investigation" } }, headers: owner_headers

    expect(response).to have_http_status(:created)
    expect(organization.investigations.find(JSON.parse(response.body)["id"])).to be_present
  end

  it "requires api:write scope to create" do
    viewer = User.create!(email: "viewer@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: viewer, role: "viewer")
    _record, viewer_token = ApiToken.issue!(organization:, user: viewer, name: "test", scopes: Membership.scopes_for("viewer"))

    post "/api/v1/investigations", params: { investigation: { name: "Blocked" } }, headers: { "Authorization" => "Bearer #{viewer_token}" }

    expect(response).to have_http_status(:forbidden)
  end
end
