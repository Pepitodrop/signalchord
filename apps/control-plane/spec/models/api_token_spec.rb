require "rails_helper"

RSpec.describe ApiToken do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }
  let!(:membership) { Membership.create!(organization:, user:, role: "analyst") }
  let!(:token) { described_class.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("analyst")).first }

  describe "#user_or_membership_disabled?" do
    it "is false for an enabled user with an enabled membership" do
      expect(token.user_or_membership_disabled?).to be(false)
    end

    it "is true when the user is disabled" do
      user.update!(disabled_at: Time.current)
      expect(token.user_or_membership_disabled?).to be(true)
    end

    it "is true when the membership is disabled" do
      membership.update!(disabled_at: Time.current)
      expect(token.user_or_membership_disabled?).to be(true)
    end

    it "is true when the membership no longer exists at all" do
      membership.destroy!
      expect(token.user_or_membership_disabled?).to be(true)
    end

    it "is false for a userless (service) token — nothing to check" do
      _record, plaintext = described_class.issue!(organization:, name: "service token", scopes: ["api:read"])
      service_token = described_class.authenticate(plaintext)

      expect(service_token.user_or_membership_disabled?).to be(false)
    end

    it "accepts a pre-resolved membership to avoid a second query" do
      membership.update!(disabled_at: Time.current)

      expect(token.user_or_membership_disabled?(membership:)).to be(true)
      expect(token.user_or_membership_disabled?(membership: nil)).to be(true) # falls back to its own lookup
    end
  end
end
