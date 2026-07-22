require "rails_helper"

RSpec.describe AlertEmailNotificationJob, type: :job do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) do
    User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:membership) { Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: true) }
  let!(:alert) do
    organization.alerts.create!(stable_id: "alert-1", title: "Signal detected", alert_score: 80, severity_code: 5)
  end

  it "sends the email and marks the delivery delivered" do
    expect {
      described_class.new.perform(alert.id, membership.id)
    }.to change(ActionMailer::Base.deliveries, :count).by(1)

    delivery = AlertEmailDelivery.find_by(alert:, membership:)
    expect(delivery.status).to eq("delivered")
  end

  it "skips delivery when the member opts out after enqueue" do
    membership.update!(email_alerts_enabled: false)

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)

    delivery = AlertEmailDelivery.find_by(alert:, membership:)
    expect(delivery.status).to eq("skipped")
    expect(delivery.last_error).to eq("member opted out of alert emails")
  end

  it "skips delivery when the membership is disabled after enqueue" do
    membership.update!(disabled_at: Time.current)

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)

    delivery = AlertEmailDelivery.find_by(alert:, membership:)
    expect(delivery.status).to eq("skipped")
    expect(delivery.last_error).to eq("membership is disabled")
  end

  it "skips delivery when the membership belongs to another organization" do
    other_organization = Organization.create!(name: "Other", slug: "other")
    other_membership = Membership.create!(
      organization: other_organization,
      user:,
      role: "viewer",
      email_alerts_enabled: true
    )

    expect {
      described_class.new.perform(alert.id, other_membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)

    delivery = AlertEmailDelivery.find_by(alert:, membership: other_membership)
    expect(delivery.status).to eq("skipped")
    expect(delivery.last_error).to eq("membership belongs to a different organization")
  end

  it "marks the delivery failed and re-raises when the mailer raises" do
    allow(AlertMailer).to receive(:alert_notification).and_raise(Net::OpenTimeout, "smtp timed out")

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.to raise_error(Net::OpenTimeout)

    delivery = AlertEmailDelivery.find_by(alert:, membership:)
    expect(delivery.status).to eq("failed")
    expect(delivery.last_error).to include("smtp timed out")
    expect(delivery.attempts).to eq(1)
  end

  it "does not resend when the delivery is already delivered (redelivery-safe)" do
    AlertEmailDelivery.create!(organization:, alert:, membership:, status: "delivered")

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)
  end

  it "does not reconsider a terminal skipped delivery on redelivery" do
    AlertEmailDelivery.create!(
      organization:,
      alert:,
      membership:,
      status: "skipped",
      last_error: "member opted out of alert emails"
    )

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)
  end

  it "does not resend when the delivery is stuck 'sending' from a prior ambiguous attempt" do
    AlertEmailDelivery.create!(organization:, alert:, membership:, status: "sending")

    expect {
      described_class.new.perform(alert.id, membership.id)
    }.not_to change(ActionMailer::Base.deliveries, :count)

    delivery = AlertEmailDelivery.find_by(alert:, membership:)
    expect(delivery.status).to eq("failed")
    expect(delivery.last_error).to match(/ambiguous outcome/)
  end
end