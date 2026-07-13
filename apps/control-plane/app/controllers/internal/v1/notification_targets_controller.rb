module Internal
  module V1
    class NotificationTargetsController < ActionController::API
      before_action :authenticate_internal!

      def create
        organization = Organization.find(params.require(:tenant_id))
        event_id = params.require(:event_id)
        alert_id = params.require(:alert_id)
        targets = organization.notification_endpoints.enabled.filter_map do |endpoint|
          delivery = organization.notification_deliveries.find_or_initialize_by(
            notification_endpoint: endpoint,
            event_id:
          )
          next if delivery.persisted? && delivery.status == "delivered"

          delivery.assign_attributes(alert_id:, status: "sending", attempts: delivery.attempts.to_i + 1)
          delivery.save!
          {
            delivery_id: delivery.id,
            endpoint_id: endpoint.id,
            platform: endpoint.platform,
            token: endpoint.delivery_token
          }
        end
        render json: { targets: }
      end

      def update
        delivery = NotificationDelivery.find(params[:id])
        delivery.update!(
          status: params.require(:status),
          provider_message_id: params[:provider_message_id],
          last_error: params[:last_error]
        )
        render json: { status: delivery.status }
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
