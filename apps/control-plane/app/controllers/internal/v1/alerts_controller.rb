module Internal
  module V1
    class AlertsController < ActionController::API
      before_action :authenticate_internal!

      def create
        event = params.permit!.to_h
        organization = Organization.find(event.fetch("tenant_id"))
        payload = event.fetch("payload")
        alert = organization.alerts.find_or_initialize_by(stable_id: payload.fetch("alert_id"))
        alert.assign_attributes(
          title: payload["title"].presence || "SignalChord intelligence alert",
          summary: payload["summary"].presence || "Policy #{payload['policy_version_id']} produced score #{payload['alert_score']}.",
          alert_score: payload.fetch("alert_score"),
          severity_code: payload.fetch("severity_code"),
          routing_code: payload.fetch("routing_code", 1),
          suppressed: payload.fetch("suppressed", false),
          evidence_ids: payload.fetch("evidence_ids", []),
          graph_path_ids: payload.fetch("graph_path_ids", []),
          policy_trace: payload.slice("policy_id", "policy_version_id", "execution_engine", "policy_source_sha256")
        )
        created = alert.new_record?

        # alert.save! and the two notification paths (push OutboxEvent enqueue,
        # per-recipient email job enqueue) are wrapped in one transaction: if
        # either enqueue raises, the alert itself rolls back too rather than
        # persisting with a silently lost notification. Without this, a raised
        # enqueue failure would leave the alert committed but Kafka redelivery
        # of alert.created.v1 would find it already persisted (created=false)
        # and skip the whole notification block forever on retry.
        ActiveRecord::Base.transaction do
          alert.save!
          if created && !alert.suppressed?
            enqueue_notification(event, alert)
            enqueue_email_notifications(alert)
          end
        end

        render json: alert, status: created ? :created : :ok
      rescue KeyError => error
        render json: { error: "invalid_event", detail: error.message }, status: :unprocessable_entity
      end

      private

      def enqueue_email_notifications(alert)
        alert.organization.memberships.enabled.where(email_alerts_enabled: true).find_each do |membership|
          AlertEmailNotificationJob.perform_later(alert.id, membership.id)
        end
      end

      def enqueue_notification(event, alert)
        OutboxEvent.enqueue!(
          organization: alert.organization,
          topic: "notification.requested.v1",
          partition_key: alert.organization_id,
          event_type: "notification.requested.v1",
          correlation_id: event.fetch("correlation_id"),
          causation_id: event.fetch("event_id"),
          payload: {
            alert_id: alert.id,
            stable_alert_id: alert.stable_id,
            title: alert.title,
            summary: alert.summary,
            severity_code: alert.severity_code,
            routing_code: alert.routing_code
          }
        )
      end

      def authenticate_internal!
        expected = ENV.fetch("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal")
        actual = request.headers["X-SignalChord-Internal-Token"].to_s
        valid = ActiveSupport::SecurityUtils.secure_compare(
          Digest::SHA256.hexdigest(actual),
          Digest::SHA256.hexdigest(expected)
        )
        return if valid

        head :unauthorized
      end
    end
  end
end
