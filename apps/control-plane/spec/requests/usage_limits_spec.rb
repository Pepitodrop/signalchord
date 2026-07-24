require "rails_helper"

RSpec.describe "usage limit", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:owner) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }
  let!(:membership) { Membership.create!(organization:, user: owner, role: "owner") }
  let!(:token) { ApiToken.issue!(organization:, user: owner, name: "test", scopes: Membership.scopes_for("owner")).last }
  let(:auth_headers) { { "Authorization" => "Bearer #{token}" } }

  describe "GET /api/v1/usage_limit" do
    it "requires owner/admin" do
      viewer = User.create!(email: "viewer@example.com", password: "correct-horse-battery-staple")
      Membership.create!(organization:, user: viewer, role: "viewer")
      _record, viewer_token = ApiToken.issue!(organization:, user: viewer, name: "test", scopes: Membership.scopes_for("viewer"))

      get "/api/v1/usage_limit", headers: { "Authorization" => "Bearer #{viewer_token}" }

      expect(response).to have_http_status(:forbidden)
    end
  end

  describe "PATCH /api/v1/usage_limit" do
    it "ignores a client-supplied billing_state (Blocker #7 regression)" do
      organization.effective_usage_limit.update!(billing_state: "suspended", source_limit: 5, watchlist_limit: 5, notification_endpoint_limit: 5, monthly_api_request_limit: 1000)

      patch "/api/v1/usage_limit", params: { usage_limit: { billing_state: "active", source_limit: 20 } }, headers: auth_headers

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["billing_state"]).to eq("suspended")
      expect(body["source_limit"]).to eq(20)
      expect(organization.usage_limit.reload.billing_state).to eq("suspended")
    end

    it "still applies ordinary limit updates" do
      patch "/api/v1/usage_limit", params: { usage_limit: { watchlist_limit: 50 } }, headers: auth_headers

      expect(response).to have_http_status(:ok)
      expect(organization.effective_usage_limit.reload.watchlist_limit).to eq(50)
    end

    it "cannot target another organization's usage limit" do
      other_org = Organization.create!(name: "Beta", slug: "beta")
      other_org.effective_usage_limit.update!(billing_state: "suspended", source_limit: 5, watchlist_limit: 5, notification_endpoint_limit: 5, monthly_api_request_limit: 1000)

      patch "/api/v1/usage_limit", params: { usage_limit: { watchlist_limit: 999 } }, headers: auth_headers

      expect(other_org.usage_limit.reload.watchlist_limit).to eq(5)
    end
  end
end
