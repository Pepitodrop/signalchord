module Api
  module V1
    class SessionsController < ApplicationController
      def index
        require_scope!("api:read")
        raise Forbidden unless current_api_token.user_id

        sessions = current_organization.api_tokens.active.where(user_id: current_api_token.user_id).order(created_at: :desc)
        render json: sessions.as_json(only: %i[id name scopes last_used_at expires_at created_at])
      end

      def destroy
        token = params[:id].present? ? session_token : current_api_token
        token.update!(revoked_at: Time.current)
        audit!(action: "session.revoked", target: token, metadata: { self_revoked: token.id == current_api_token.id })
        head :no_content
      end

      private

      def session_token
        raise Forbidden unless current_api_token.user_id

        current_organization.api_tokens.active.find_by!(id: params[:id], user_id: current_api_token.user_id)
      end
    end
  end
end
