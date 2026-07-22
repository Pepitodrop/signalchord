require "rails_helper"

RSpec.describe AlertMailer, type: :mailer do
  describe "#alert_notification" do
    let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
    let(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple") }
    let(:policy) { Policy.create!(organization:, name: "Watchlist Novelty") }
    let(:alert) do
      organization.alerts.create!(
        stable_id: "alert-1", title: "Signal detected", summary: "Something changed.",
        alert_score: 80, severity_code: 5, evidence_ids: %w[ev-1 ev-2], policy:
      )
    end
    let(:mail) { AlertMailer.alert_notification(user, alert) }

    it "addresses the email to the user" do
      expect(mail.to).to eq([user.email])
    end

    it "has a subject naming the alert" do
      expect(mail.subject).to eq("New SignalChord alert: Signal detected")
    end

    it "includes title, prioritization score/severity, policy name, and evidence count" do
      expect(mail.text_part.body.to_s).to include("Signal detected", "Prioritization score 80", "severity 5", "Watchlist Novelty", "2 evidence records")
      expect(mail.html_part.body.to_s).to include("Signal detected", "Watchlist Novelty")
    end

    it "omits the policy line when the alert has no policy" do
      unlinked_alert = organization.alerts.create!(stable_id: "alert-2", title: "No policy", alert_score: 10, severity_code: 1)

      mail = AlertMailer.alert_notification(user, unlinked_alert)

      expect(mail.text_part.body.to_s).not_to include("Triggered policy")
    end
  end
end
