module Api
  module V1
    class AlertsController < ApplicationController
      before_action :alert, only: %i[show update]

      def index
        scope = current_organization.alerts.order(created_at: :desc)
        scope = scope.where(read_at: nil) if params[:unread] == "true"
        render json: scope.limit([params.fetch(:limit, 100).to_i, 250].min)
      end
      def show = render json: @alert
      def update
        require_scope!("api:write")
        @alert.update!(params.require(:alert).permit(:read_at, :review_status, :relevance_feedback))
        audit!(action: "alert.updated", target: @alert)
        render json: @alert
      end

      private

      def alert = @alert = current_organization.alerts.find(params[:id])
    end
  end
end
