class AlertMailer < ApplicationMailer
  def alert_notification(user, alert)
    @user = user
    @alert = alert
    @policy_name = alert.policy&.name
    @evidence_count = alert.evidence_ids.size
    @dashboard_url = ENV.fetch("PUBLIC_WEB_URL", "http://localhost:5173")

    mail(to: user.email, subject: "New SignalChord alert: #{alert.title}")
  end
end
