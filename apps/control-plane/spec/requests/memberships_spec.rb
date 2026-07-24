require "rails_helper"

RSpec.describe "memberships", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:owner_user) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }
  let!(:owner_membership) { Membership.create!(organization:, user: owner_user, role: "owner") }
  let!(:owner_token) { ApiToken.issue!(organization:, user: owner_user, name: "test", scopes: Membership.scopes_for("owner")).last }
  let(:owner_headers) { { "Authorization" => "Bearer #{owner_token}" } }

  let!(:member_user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }
  let!(:member_membership) { Membership.create!(organization:, user: member_user, role: "owner") }
  let!(:member_token) { ApiToken.issue!(organization:, user: member_user, name: "test", scopes: Membership.scopes_for("owner")).last }

  describe "GET /api/v1/memberships" do
    it "requires owner/admin" do
      viewer = User.create!(email: "viewer@example.com", password: "correct-horse-battery-staple")
      Membership.create!(organization:, user: viewer, role: "viewer")
      _record, viewer_token = ApiToken.issue!(organization:, user: viewer, name: "test", scopes: Membership.scopes_for("viewer"))

      get "/api/v1/memberships", headers: { "Authorization" => "Bearer #{viewer_token}" }

      expect(response).to have_http_status(:forbidden)
    end

    it "never leaks another organization's memberships" do
      other_org = Organization.create!(name: "Beta", slug: "beta")
      other_user = User.create!(email: "beta@example.com", password: "correct-horse-battery-staple")
      Membership.create!(organization: other_org, user: other_user, role: "owner")

      get "/api/v1/memberships", headers: owner_headers

      ids = JSON.parse(response.body).map { |row| row.fetch("id") }
      expect(ids).to include(member_membership.id)
      expect(ids).not_to include(other_user.id)
    end
  end

  describe "PATCH /api/v1/memberships/:id" do
    it "revokes the member's active token immediately when disabled via PATCH, not just DELETE (Blocker #3 regression)" do
      expect {
        patch "/api/v1/memberships/#{member_membership.id}", params: { membership: { disabled: true } }, headers: owner_headers
      }.to change { ApiToken.active.where(user_id: member_user.id).count }.from(1).to(0)

      expect(response).to have_http_status(:ok)
      get "/api/v1/organizations", headers: { "Authorization" => "Bearer #{member_token}" }
      expect(response).to have_http_status(:unauthorized)
    end

    it "does not re-revoke tokens when patching a field other than disabled" do
      expect {
        patch "/api/v1/memberships/#{member_membership.id}", params: { membership: { role: "admin" } }, headers: owner_headers
      }.not_to change { ApiToken.active.where(user_id: member_user.id).count }
    end

    it "does not revoke tokens when re-enabling an already-disabled membership" do
      member_membership.update!(disabled_at: Time.current)

      expect {
        patch "/api/v1/memberships/#{member_membership.id}", params: { membership: { disabled: false } }, headers: owner_headers
      }.not_to change { ApiToken.where(user_id: member_user.id).count }
    end

    it "a role downgrade takes effect on the pre-existing token's very next request, without re-login (Blocker #2 regression)" do
      # member starts as "owner" (scopes ["*"]) — downgrade to "viewer" and
      # confirm the SAME still-active token can no longer write, proving
      # require_scope! now derives from the live role, not the token's
      # issuance-time scopes snapshot.
      patch "/api/v1/memberships/#{member_membership.id}", params: { membership: { role: "viewer" } }, headers: owner_headers
      expect(response).to have_http_status(:ok)

      post "/api/v1/watchlists",
           params: { watchlist: { name: "Should be blocked" } },
           headers: { "Authorization" => "Bearer #{member_token}" }

      expect(response).to have_http_status(:forbidden)
    end

    it "an upgrade also takes effect immediately on the pre-existing token" do
      viewer = User.create!(email: "upgrade@example.com", password: "correct-horse-battery-staple")
      viewer_membership = Membership.create!(organization:, user: viewer, role: "viewer")
      _record, viewer_token = ApiToken.issue!(organization:, user: viewer, name: "test", scopes: Membership.scopes_for("viewer"))

      patch "/api/v1/memberships/#{viewer_membership.id}", params: { membership: { role: "admin" } }, headers: owner_headers
      expect(response).to have_http_status(:ok)

      post "/api/v1/watchlists",
           params: { watchlist: { name: "Now allowed" } },
           headers: { "Authorization" => "Bearer #{viewer_token}" }

      expect(response).to have_http_status(:created)
    end

    it "prevents disabling the last enabled owner" do
      member_membership.update!(disabled_at: Time.current) # leave owner_membership as the sole enabled owner

      patch "/api/v1/memberships/#{owner_membership.id}", params: { membership: { disabled: true } }, headers: owner_headers

      expect(response).to have_http_status(:forbidden)
      expect(owner_membership.reload.disabled_at).to be_nil
    end
  end

  describe "DELETE /api/v1/memberships/:id" do
    it "disables the membership and revokes tokens" do
      delete "/api/v1/memberships/#{member_membership.id}", headers: owner_headers

      expect(response).to have_http_status(:no_content)
      expect(member_membership.reload.disabled_at).to be_present
      expect(ApiToken.active.where(user_id: member_user.id)).to be_empty
    end

    it "cannot target another organization's membership by guessed id" do
      other_org = Organization.create!(name: "Beta", slug: "beta")
      other_user = User.create!(email: "beta-owner@example.com", password: "correct-horse-battery-staple")
      other_membership = Membership.create!(organization: other_org, user: other_user, role: "owner")

      delete "/api/v1/memberships/#{other_membership.id}", headers: owner_headers

      expect(response).to have_http_status(:not_found)
      expect(other_membership.reload.disabled_at).to be_nil
    end
  end
end
