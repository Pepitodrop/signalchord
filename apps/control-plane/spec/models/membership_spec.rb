require "rails_helper"

RSpec.describe Membership, type: :model do
  describe ".scopes_for" do
    it "grants full scope to owner" do
      expect(Membership.scopes_for("owner")).to eq(["*"])
    end

    it "grants full scope to admin" do
      expect(Membership.scopes_for("admin")).to eq(["*"])
    end

    it "grants read+write scope to analyst" do
      expect(Membership.scopes_for("analyst")).to eq(%w[api:read api:write])
    end

    it "grants read+write scope to reviewer" do
      expect(Membership.scopes_for("reviewer")).to eq(%w[api:read api:write])
    end

    it "grants read-only scope to viewer" do
      expect(Membership.scopes_for("viewer")).to eq(["api:read"])
    end

    it "defaults unknown roles to read-only scope" do
      expect(Membership.scopes_for("unknown")).to eq(["api:read"])
    end
  end

  describe ".enabled" do
    let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
    let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple") }
    let!(:active_membership) { Membership.create!(organization:, user:, role: "viewer") }

    it "includes memberships with no disabled_at" do
      expect(Membership.enabled).to include(active_membership)
    end

    it "excludes disabled memberships" do
      active_membership.update!(disabled_at: Time.current)
      expect(Membership.enabled).not_to include(active_membership)
    end
  end
end
