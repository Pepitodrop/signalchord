require "rails_helper"

RSpec.describe "email verification", type: :request do
  let!(:user) { User.create!(email: "pending@example.com", password: "correct-horse-battery-staple") }

  describe "POST /api/v1/email_verifications" do
    it "verifies a valid unexpired token" do
      token = user.generate_token_for(:email_verification)

      post "/api/v1/email_verifications", params: { token: }

      expect(response).to have_http_status(:ok)
      expect(user.reload.email_verified?).to eq(true)
    end

    it "rejects an expired token" do
      token = user.generate_token_for(:email_verification)
      travel_to((ENV.fetch("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24).to_i.hours + 1.minute).from_now) do
        post "/api/v1/email_verifications", params: { token: }
      end

      expect(response).to have_http_status(:unauthorized)
      expect(user.reload.email_verified?).to eq(false)
    end

    it "rejects a malformed token" do
      post "/api/v1/email_verifications", params: { token: "not-a-real-token" }
      expect(response).to have_http_status(:unauthorized)
    end

    it "rejects replaying the same token after it has already been used (single-use)" do
      token = user.generate_token_for(:email_verification)

      post "/api/v1/email_verifications", params: { token: }
      expect(response).to have_http_status(:ok)

      post "/api/v1/email_verifications", params: { token: }
      expect(response).to have_http_status(:unauthorized)
    end
  end

  describe "POST /api/v1/email_verifications/resend" do
    it "sends a new verification email for an existing unverified user" do
      expect {
        post "/api/v1/email_verifications/resend", params: { email: user.email }
      }.to change(ActionMailer::Base.deliveries, :count).by(1)

      expect(response).to have_http_status(:ok)
    end

    it "invalidates a previously issued token once resent" do
      old_token = user.generate_token_for(:email_verification)

      post "/api/v1/email_verifications/resend", params: { email: user.email }

      post "/api/v1/email_verifications", params: { token: old_token }
      expect(response).to have_http_status(:unauthorized)
    end

    it "returns the identical response for a nonexistent email (no enumeration)" do
      post "/api/v1/email_verifications/resend", params: { email: "nobody@example.com" }
      nonexistent_body = response.body
      nonexistent_status = response.status

      post "/api/v1/email_verifications/resend", params: { email: user.email }

      expect(response.status).to eq(nonexistent_status)
      expect(response.body).to eq(nonexistent_body)
    end

    it "does not send an email for an already-verified user, but still returns the generic response" do
      user.update!(email_verified_at: Time.current)

      expect {
        post "/api/v1/email_verifications/resend", params: { email: user.email }
      }.not_to change(ActionMailer::Base.deliveries, :count)

      expect(response).to have_http_status(:ok)
    end
  end
end
