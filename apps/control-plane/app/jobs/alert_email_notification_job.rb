# Sends one alert-notification email to one membership. One job per
# recipient (not one job looping over all recipients) so a single
# recipient's failure/retry never touches another recipient's delivery.
#
#   perform(alert_id, membership_id)
#     |
#     +-- delivery.status == "delivered"?
#     |     -> return (already sent; Sidekiq at-least-once redelivery-safe)
#     |
#     +-- delivery.status == "sending"?
#     |     -> a previous run got far enough to attempt the send but never
#     |        confirmed the outcome (e.g. the DB write after a successful
#     |        SMTP send failed). Raw SMTP has no provider-side idempotency
#     |        key, so resending here risks a real duplicate. Mark "failed"
#     |        with an ambiguous-outcome message instead of guessing.
#     |
#     +-- otherwise (new / "pending" / "failed") ->
#           delivery.update!(status: "sending")   [committed before sending]
#           AlertMailer.alert_notification(user, alert).deliver_now
#             success -> delivery.update!(status: "delivered")
#             error   -> delivery.update!(status: "failed", last_error:, attempts: +1)
#                        raise (Sidekiq retries, capped at 5 attempts)
class AlertEmailNotificationJob < ApplicationJob
  sidekiq_options retry: 5

  AMBIGUOUS_OUTCOME_ERROR = "ambiguous outcome from a previous attempt — resend requires manual confirmation".freeze

  def perform(alert_id, membership_id)
    alert = Alert.find(alert_id)
    membership = Membership.find(membership_id)
    delivery = AlertEmailDelivery.find_or_initialize_by(alert:, membership:)
    delivery.organization ||= alert.organization

    return if delivery.status == "delivered"

    if delivery.status == "sending"
      delivery.update!(status: "failed", last_error: AMBIGUOUS_OUTCOME_ERROR)
      return
    end

    delivery.update!(status: "sending")

    begin
      AlertMailer.alert_notification(membership.user, alert).deliver_now
      delivery.update!(status: "delivered")
    rescue StandardError => error
      delivery.update!(status: "failed", last_error: error.message, attempts: delivery.attempts + 1)
      raise
    end
  end
end
