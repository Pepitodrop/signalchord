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
          policy_trace: payload.slice("policy_id", "policy_version_id", "execution_engine", "policy_source_sha256", "trace_hash", "instructions_executed")
        )
        created = alert.new_record?
        alert.save!
        render json: alert, status: created ? :created : :ok
      rescue KeyError => error
        render json: { error: "invalid_event", detail: error.message }, status: :unprocessable_entity
      end

      private

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
