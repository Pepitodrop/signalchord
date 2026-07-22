require "rails_helper"

RSpec.describe OnboardingMailer, type: :mailer do
  describe "#verification_email" do
    let(:user) { User.create!(email: "new-user@example.com", password: "correct-horse-battery-staple") }
    let(:token) { user.generate_token_for(:email_verification) }
    let(:mail) { OnboardingMailer.verification_email(user, token) }

    it "addresses the email to the user" do
      expect(mail.to).to eq([user.email])
    end

    it "has a clear subject" do
      expect(mail.subject).to eq("Verify your SignalChord account")
    end

    it "includes a verification link with the token" do
      expect(mail.text_part.body.to_s).to include(token)
      expect(mail.html_part.body.to_s).to include(token)
    end
  end
end
