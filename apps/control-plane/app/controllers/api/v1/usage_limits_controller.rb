module Api
  module V1
    class UsageLimitsController < ApplicationController
      before_action -> { require_role!("owner", "admin") }

      def show
        render json: current_organization.effective_usage_limit
      end

      def update
        limit = current_organization.effective_usage_limit
        limit.assign_attributes(limit_params)
        limit.save!
        audit!(action: "usage_limit.updated", target: limit, metadata: limit_params)
        render json: limit
      end

      private

      def limit_params
        params.require(:usage_limit).permit(
          :billing_state,
          :source_limit,
          :watchlist_limit,
          :notification_endpoint_limit,
          :monthly_api_request_limit,
          metadata: {}
        )
      end
    end
  end
end
