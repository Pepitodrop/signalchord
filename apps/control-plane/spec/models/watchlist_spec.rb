require "rails_helper"

RSpec.describe Watchlist, type: :model do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:other_organization) { Organization.create!(name: "Other Co", slug: "other-co") }

  describe "idempotency_key uniqueness" do
    it "allows multiple watchlists with no idempotency_key (ordinary, non-idempotent creates)" do
      organization.watchlists.create!(name: "First")
      expect {
        organization.watchlists.create!(name: "Second")
      }.not_to raise_error
    end

    it "rejects a duplicate idempotency_key within the same organization" do
      organization.watchlists.create!(name: "First", idempotency_key: "key-1")

      duplicate = organization.watchlists.new(name: "Second", idempotency_key: "key-1")

      expect(duplicate).not_to be_valid
      expect(duplicate.errors[:idempotency_key]).to be_present
    end

    it "allows the same idempotency_key across different organizations" do
      organization.watchlists.create!(name: "First", idempotency_key: "shared-key")

      other = other_organization.watchlists.new(name: "First", idempotency_key: "shared-key")

      expect(other).to be_valid
    end
  end
end
