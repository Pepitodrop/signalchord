require "rails_helper"

RSpec.describe "web session (cookie auth)", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:verified_user) do
    User.create!(email: "verified@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:unverified_user) { User.create!(email: "unverified@example.com", password: "correct-horse-battery-staple") }

  describe "POST /api/v1/auth/web_session" do
    it "rejects a wrong password" do
      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "wrong-password" }
      expect(response).to have_http_status(:unauthorized)
    end

    it "rejects a nonexistent email with the same error as a wrong password (no enumeration)" do
      post "/api/v1/auth/web_session", params: { email: "nobody@example.com", password: "whatever" }
      expect(response).to have_http_status(:unauthorized)
      expect(JSON.parse(response.body)["error"]).to eq("invalid_credentials")
    end

    it "rejects an unverified user even with the correct password" do
      post "/api/v1/auth/web_session", params: { email: unverified_user.email, password: "correct-horse-battery-staple" }
      expect(response).to have_http_status(:forbidden)
    end

    it "returns workspace_required and sets NO cookie for a verified user with zero memberships" do
      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body)["status"]).to eq("workspace_required")
      expect(response.cookies[CookieSession::SESSION_COOKIE_NAME]).to be_nil
    end

    it "sets the session cookie and returns the role for a verified user with an enabled membership" do
      Membership.create!(organization:, user: verified_user, role: "admin")

      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      expect(response).to have_http_status(:ok)
      body = JSON.parse(response.body)
      expect(body["status"]).to eq("authenticated")
      expect(body["role"]).to eq("admin")
      expect(response.cookies[CookieSession::SESSION_COOKIE_NAME]).to be_present
    end

    it "ignores a disabled membership when deciding workspace_required vs authenticated" do
      Membership.create!(organization:, user: verified_user, role: "admin", disabled_at: Time.current)

      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      expect(JSON.parse(response.body)["status"]).to eq("workspace_required")
    end

    it "picks the most recently created enabled membership when a user has more than one" do
      older_org = Organization.create!(name: "Older", slug: "older")
      Membership.create!(organization: older_org, user: verified_user, role: "viewer")
      travel(1.second) do
        Membership.create!(organization:, user: verified_user, role: "owner")
      end

      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      expect(JSON.parse(response.body)["role"]).to eq("owner")
    end

    it "authenticates the resulting cookie against a real tenant-scoped endpoint" do
      Membership.create!(organization:, user: verified_user, role: "admin")
      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      get "/api/v1/organizations"

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body).first["id"]).to eq(organization.id)
    end
  end

  describe "DELETE /api/v1/auth/web_session" do
    it "revokes the token and clears the cookie" do
      Membership.create!(organization:, user: verified_user, role: "admin")
      post "/api/v1/auth/web_session", params: { email: verified_user.email, password: "correct-horse-battery-staple" }

      delete "/api/v1/auth/web_session"
      expect(response).to have_http_status(:no_content)

      get "/api/v1/organizations"
      expect(response).to have_http_status(:unauthorized)
    end

    it "is idempotent when there is no session to revoke" do
      delete "/api/v1/auth/web_session"
      expect(response).to have_http_status(:no_content)
    end
  end
end
