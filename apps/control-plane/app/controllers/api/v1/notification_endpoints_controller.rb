module Api
  module V1
    class NotificationEndpointsController < ApplicationController
      before_action -> { require_scope!("api:write") }
      before_action :endpoint, only: :destroy

      def index
        render json: current_organization.notification_endpoints.where(user_id: current_api_token.user_id).as_json(
          only: %i[id platform enabled last_seen_at created_at]
        )
      end

      def create
        raise Forbidden unless current_api_token.user_id

        endpoint = NotificationEndpoint.register!(
          organization: current_organization,
          user: User.find(current_api_token.user_id),
          platform: params.require(:platform),
          token: params.require(:token)
        )
        audit!(action: "notification_endpoint.registered", target: endpoint)
        render json: endpoint.as_json(only: %i[id platform enabled last_seen_at created_at]), status: :created
      end

      def destroy
        @endpoint.update!(enabled: false)
        audit!(action: "notification_endpoint.disabled", target: @endpoint)
        head :no_content
      end

      private

      def endpoint
        @endpoint = current_organization.notification_endpoints.find_by!(
          id: params[:id],
          user_id: current_api_token.user_id
        )
      end
    end
  end
end
