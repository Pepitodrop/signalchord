require "rails_helper"

RSpec.describe "invitations", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:owner_user) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple") }
  let!(:owner_membership) { Membership.create!(organization:, user: owner_user, role: "owner") }
  let!(:owner_token) do
    _record, plaintext = ApiToken.issue!(organization:, user: owner_user, name: "owner session", scopes: ["*"])
    plaintext
  end
  let(:owner_headers) { { "Authorization" => "Bearer #{owner_token}" } }

  describe "POST /api/v1/invitations/accept" do
    let!(:invitation_token) do
      _record, plaintext = Invitation.issue!(
        organization:, email: "new-teammate@example.com", role: "analyst", invited_by_user_id: owner_user.id
      )
      plaintext
    end

    it "creates a new user, an enabled membership, and issues a session" do
      post "/api/v1/invitations/accept",
           params: { invitation_token:, password: "another-correct-horse" }

      expect(response).to have_http_status(:created)
      body = JSON.parse(response.body)
      expect(body["role"]).to eq("analyst")
      expect(body["scopes"]).to eq(%w[api:read api:write])

      membership = Membership.find_by(organization:, user: User.find_by(email: "new-teammate@example.com"))
      expect(membership).to be_present
      expect(membership.disabled_at).to be_nil
    end

    it "marks the accepting user's email as verified (regression fix — was previously never set)" do
      post "/api/v1/invitations/accept",
           params: { invitation_token:, password: "another-correct-horse" }

      user = User.find_by(email: "new-teammate@example.com")
      expect(user.email_verified?).to eq(true)
    end

    it "does not overwrite an existing verification timestamp for a user who already verified elsewhere" do
      existing_time = 3.days.ago
      User.create!(email: "new-teammate@example.com", password: "some-existing-password", email_verified_at: existing_time)

      post "/api/v1/invitations/accept",
           params: { invitation_token:, password: "another-correct-horse" }

      user = User.find_by(email: "new-teammate@example.com")
      expect(user.email_verified_at).to be_within(1.second).of(existing_time)
    end

    it "rejects an invalid invitation token" do
      post "/api/v1/invitations/accept", params: { invitation_token: "sc_inv_bogus", password: "another-correct-horse" }
      expect(response).to have_http_status(:unauthorized)
    end
  end

  describe "POST /api/v1/invitations (issue an invitation)" do
    it "uses the consolidated Membership.scopes_for mapping consistently with AuthController (regression)" do
      post "/api/v1/invitations",
           params: { email: "another@example.com", role: "admin" },
           headers: owner_headers
      expect(response).to have_http_status(:created)

      invitation_token = JSON.parse(response.body).fetch("invitation_token")
      post "/api/v1/invitations/accept", params: { invitation_token:, password: "another-correct-horse" }

      expect(response).to have_http_status(:created)
      expect(JSON.parse(response.body)["scopes"]).to eq(["*"]), "admin role must still resolve to full scope after scopes_for consolidation"
    end
  end
end
