require "rails_helper"

RSpec.describe AlertEmailDelivery, type: :model do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) do
    User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:membership) { Membership.create!(organization:, user:, role: "viewer") }
  let!(:other_user) do
    User.create!(email: "other@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:other_membership) { Membership.create!(organization:, user: other_user, role: "viewer") }
  let!(:alert) do
    organization.alerts.create!(stable_id: "alert-1", title: "Signal detected", alert_score: 80, severity_code: 5)
  end
  let!(:other_alert) do
    organization.alerts.create!(stable_id: "alert-2", title: "Another signal", alert_score: 40, severity_code: 2)
  end

  it "requires status to be one of the known values" do
    delivery = AlertEmailDelivery.new(organization:, alert:, membership:, status: "not_a_real_status")

    expect(delivery).not_to be_valid
    expect(delivery.errors[:status]).to be_present
  end

  it "allows the same alert across different memberships" do
    organization.alert_email_deliveries.create!(organization:, alert:, membership:, status: "pending")

    other = organization.alert_email_deliveries.new(organization:, alert:, membership: other_membership, status: "pending")

    expect(other).to be_valid
  end

  it "allows the same membership across different alerts" do
    organization.alert_email_deliveries.create!(organization:, alert:, membership:, status: "pending")

    other = organization.alert_email_deliveries.new(organization:, alert: other_alert, membership:, status: "pending")

    expect(other).to be_valid
  end

  it "rejects a duplicate (alert, membership) pair" do
    organization.alert_email_deliveries.create!(organization:, alert:, membership:, status: "pending")

    duplicate = organization.alert_email_deliveries.new(organization:, alert:, membership:, status: "pending")

    expect(duplicate).not_to be_valid
    expect(duplicate.errors[:alert_id]).to be_present
  end
end
