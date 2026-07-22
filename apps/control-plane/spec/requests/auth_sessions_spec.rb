require "rails_helper"

RSpec.describe "POST /api/v1/auth/session", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple") }

  def login_as(role)
    Membership.create!(organization:, user:, role:)
    post "/api/v1/auth/session",
         params: { email: user.email, password: "correct-horse-battery-staple", organization_slug: organization.slug }
  end

  # Regression coverage for Membership.scopes_for consolidation (previously duplicated
  # inline in this controller and in InvitationsController, which silently disagreed
  # on the owner case).
  {
    "owner" => ["*"],
    "admin" => ["*"],
    "analyst" => %w[api:read api:write],
    "reviewer" => %w[api:read api:write],
    "viewer" => ["api:read"]
  }.each do |role, expected_scopes|
    it "issues #{expected_scopes.inspect} scopes for role #{role.inspect} (unchanged after scopes_for consolidation)" do
      login_as(role)
      expect(response).to have_http_status(:created)
      expect(JSON.parse(response.body)["scopes"]).to eq(expected_scopes)
    end
  end
end
