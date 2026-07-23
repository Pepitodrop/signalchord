module Api
  module V1
    class WebSessionsController < ActionController::API
      include CookieSession
      include DummyTimingAuthentication

      rescue_from ActionController::ParameterMissing, with: ->(error) {
        render json: { error: "invalid_request", detail: error.message }, status: :bad_request
      }

      # No pending/intermediate session of any kind (decision 5, reconfirmed
      # against an outside-voice challenge in eng review). A verified user
      # with zero workspaces gets NO cookie here at all — just a stateless
      # signal telling the frontend to hold the credentials in memory and
      # bundle them into organizations#create, which re-validates fresh.
      def create
        email = params.require(:email).to_s.strip.downcase
        password = params.require(:password).to_s

        user = User.find_by(email:)
        unless authenticate_with_dummy_timing(user, password) && !user&.disabled?
          return render json: { error: "invalid_credentials" }, status: :unauthorized
        end
        return render json: { error: "verification_required" }, status: :forbidden unless user.email_verified?

        memberships = user.memberships.enabled
        return render json: { status: "workspace_required" }, status: :ok if memberships.none?

        # >1 active membership is unreachable through self-serve signup alone,
        # only via the untouched Invitation flow adding a second org. Picking
        # the most recent is a documented, deliberate limitation — a real
        # org-picker is tracked in TODOS.md, not built here.
        membership = memberships.order(created_at: :desc).first
        organization = membership.organization
        token, plaintext = ApiToken.issue!(
          organization:,
          user:,
          name: "Web session #{request.remote_ip}",
          scopes: Membership.scopes_for(membership.role),
          expires_at: 30.days.from_now
        )
        organization.audit_events.create!(
          actor_user_id: user.id,
          action: "session.created",
          target_type: "ApiToken",
          target_id: token.id,
          request_id: request.request_id,
          metadata: { role: membership.role, via: "web_session" },
          occurred_at: Time.current
        )
        write_session_cookie(plaintext)
        render json: { status: "authenticated", role: membership.role }, status: :ok
      end

      def destroy
        plaintext = bearer_token_from_cookie
        ApiToken.authenticate(plaintext)&.update!(revoked_at: Time.current) if plaintext
        clear_session_cookie
        head :no_content
      end
    end
  end
end
