module Internal
  module V1
    class TokensController < ActionController::API
      before_action :authenticate_internal!

      def show
        plaintext = request.authorization.to_s.delete_prefix("Bearer ").presence
        token = ApiToken.authenticate(plaintext)
        return render json: { error: "unauthorized" }, status: :unauthorized unless token
        # Defense-in-depth for services/realtime-gateway's SSE auth: a
        # disabled user/membership must get a non-2xx here, since the Go
        # consumer already treats any non-200 as a hard failure and denies
        # the connection — no Go-side changes needed for this to take effect.
        return render json: { error: "forbidden" }, status: :forbidden if token.user_or_membership_disabled?

        render json: {
          organization_id: token.organization_id,
          user_id: token.user_id,
          scopes: token.scopes,
          expires_at: token.expires_at
        }
      end

      private

      def authenticate_internal!
        expected = ENV.fetch("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal")
        actual = request.headers["X-SignalChord-Internal-Token"].to_s
        return if ActiveSupport::SecurityUtils.secure_compare(
          Digest::SHA256.hexdigest(actual),
          Digest::SHA256.hexdigest(expected)
        )

        head :unauthorized
      end
    end
  end
end
