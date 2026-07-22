require "rails_helper"

RSpec.describe User, type: :model do
  describe "#email_verified?" do
    it "is false when email_verified_at is nil" do
      user = User.new(email_verified_at: nil)
      expect(user.email_verified?).to eq(false)
    end

    it "is true when email_verified_at is set" do
      user = User.new(email_verified_at: Time.current)
      expect(user.email_verified?).to eq(true)
    end
  end
end
