class OnboardingMailer < ApplicationMailer
  def verification_email(user, token)
    @user = user
    @verification_url = "#{ENV.fetch('PUBLIC_WEB_URL', 'http://localhost:5173')}/verify-email?token=#{token}"
    @ttl_hours = ENV.fetch("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24).to_i

    mail(to: user.email, subject: "Verify your SignalChord account")
  end
end
