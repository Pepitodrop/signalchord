require "rails_helper"

RSpec.describe "policies", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:owner) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user: owner, role: "owner") }
  let!(:token) { ApiToken.issue!(organization:, user: owner, name: "test", scopes: Membership.scopes_for("owner")).last }
  let(:owner_headers) { { "Authorization" => "Bearer #{token}" } }
  let!(:own_record) { organization.policies.create!(name: "Alpha policy") }

  let!(:other_organization) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:other_record) { other_organization.policies.create!(name: "Beta policy") }

  let(:index_path) { "/api/v1/policies" }
  let(:show_path) { ->(id) { "/api/v1/policies/#{id}" } }
  let(:update_path) { ->(id) { "/api/v1/policies/#{id}" } }
  let(:update_params) { { policy: { name: "hijacked" } } }

  include_examples "a tenant-isolated resource"

  it "requires owner/admin (not just api:write scope) to update" do
    analyst = User.create!(email: "analyst@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: analyst, role: "analyst")
    _record, analyst_token = ApiToken.issue!(organization:, user: analyst, name: "test", scopes: Membership.scopes_for("analyst"))

    patch "/api/v1/policies/#{own_record.id}", params: { policy: { name: "changed" } }, headers: { "Authorization" => "Bearer #{analyst_token}" }

    expect(response).to have_http_status(:forbidden)
    expect(own_record.reload.name).to eq("Alpha policy")
  end

  it "allows analyst/reviewer to read policies (api:read only)" do
    analyst = User.create!(email: "analyst2@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: analyst, role: "analyst")
    _record, analyst_token = ApiToken.issue!(organization:, user: analyst, name: "test", scopes: Membership.scopes_for("analyst"))

    get "/api/v1/policies", headers: { "Authorization" => "Bearer #{analyst_token}" }

    expect(response).to have_http_status(:ok)
  end
end
