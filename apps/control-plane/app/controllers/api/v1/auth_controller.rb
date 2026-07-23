module Api
  module V1
    class AuthController < ActionController::API
      include DummyTimingAuthentication

      rescue_from ActionController::ParameterMissing, with: ->(error) {
        render json: { error: "invalid_request", detail: error.message }, status: :bad_request
      }

      def create
        email = params.require(:email).to_s.strip.downcase
        password = params.require(:password).to_s
        organization_slug = params.require(:organization_slug).to_s

        user = User.find_by(email:)
        organization = Organization.find_by(slug: organization_slug)
        membership = Membership.find_by(user:, organization:) if user && organization
        unless authenticate_with_dummy_timing(user, password) && membership && user.disabled_at.nil? && membership.disabled_at.nil?
          return render json: { error: "invalid_credentials" }, status: :unauthorized
        end

        token, plaintext = ApiToken.issue!(
          organization:,
          user:,
          name: "Session #{request.remote_ip}",
          scopes: Membership.scopes_for(membership.role),
          expires_at: 30.days.from_now
        )
        organization.audit_events.create!(
          actor_user_id: user.id,
          action: "session.created",
          target_type: "ApiToken",
          target_id: token.id,
          request_id: request.request_id,
          metadata: { role: membership.role },
          occurred_at: Time.current
        )
        render json: {
          access_token: plaintext,
          token_type: "Bearer",
          expires_at: token.expires_at,
          organization: organization.as_json(only: %i[id name slug]),
          user: user.as_json(only: %i[id email display_name]),
          role: membership.role,
          scopes: token.scopes
        }, status: :created
      end
    end
  end
end
