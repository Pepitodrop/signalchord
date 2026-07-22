module Api
  module V1
    class EmailVerificationsController < ActionController::API
      rescue_from ActionController::ParameterMissing, with: ->(error) {
        render json: { error: "invalid_request", detail: error.message }, status: :bad_request
      }

      # Single-use falls out of User.generates_token_for's scope block for
      # free: once email_verified_at changes below, this exact token (and any
      # other outstanding token for this user) stops matching, so replaying it
      # after a successful verify always fails from this point on.
      def create
        token = params.require(:token).to_s
        user = User.find_by_token_for(:email_verification, token)
        return render json: { error: "invalid_or_expired_token" }, status: :unauthorized unless user

        user.update!(email_verified_at: Time.current)
        render json: { email: user.email, message: "email verified" }, status: :ok
      end

      # Anti-enumeration: identical response whether the account doesn't
      # exist, is already verified, or a new link genuinely just went out.
      def resend
        email = params.require(:email).to_s.strip.downcase
        user = User.find_by(email:)
        user.send_verification_email! if user && !user.email_verified?

        render json: {
          message: "if an account with that email exists and needs verification, we've sent a new link"
        }, status: :ok
      end
    end
  end
end
