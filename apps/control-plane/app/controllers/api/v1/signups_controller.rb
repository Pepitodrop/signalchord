require "digest"

module Api
  module V1
    class SignupsController < ActionController::API
      rescue_from ActionController::ParameterMissing, with: ->(error) {
        render json: { error: "invalid_request", detail: error.message }, status: :bad_request
      }
      rescue_from ActiveRecord::RecordInvalid, with: ->(error) {
        render json: { error: "validation_failed", details: error.record.errors.to_hash }, status: :unprocessable_entity
      }
      # A race between two identical concurrent signups can both pass Rails'
      # own uniqueness validation before either commits; the DB's unique index
      # on users.email is the actual backstop and raises this distinct error
      # class, not RecordInvalid. Without this rescue it would surface as an
      # unhandled 500 instead of the same clean 422 a normal duplicate gets.
      rescue_from ActiveRecord::RecordNotUnique, with: -> {
        render json: { error: "validation_failed", details: { email: ["has already been taken"] } }, status: :unprocessable_entity
      }

      def create
        return unless verify_beta_access_code!

        user = User.create!(
          email: params.require(:email).to_s,
          password: params.require(:password).to_s,
          display_name: params[:display_name].presence
        )
        user.send_verification_email!

        render json: { email: user.email, message: "check your email to verify your account" }, status: :created
      end

      private

      def verify_beta_access_code!
        # params.require treats a blank value the same as an absent key
        # (ParameterMissing -> 400), which would misreport "no code
        # submitted" as a request error rather than "wrong/blank code" (401).
        # Only a genuinely absent key is a malformed request; present-but-blank
        # is a credential the fail-closed check below correctly rejects.
        raise ActionController::ParameterMissing, :beta_access_code unless params.key?(:beta_access_code)

        submitted = params[:beta_access_code].to_s
        configured = ENV["BETA_ACCESS_CODE"].to_s

        if configured.blank? || !codes_match?(submitted, configured)
          render json: { error: "invalid_beta_access_code" }, status: :unauthorized
          return false
        end

        true
      end

      # Hash both sides to a fixed-length digest before the constant-time
      # compare, so a mismatched submitted-code length never leaks timing
      # information about the configured code's actual length.
      def codes_match?(submitted, configured)
        ActiveSupport::SecurityUtils.secure_compare(
          Digest::SHA256.hexdigest(submitted),
          Digest::SHA256.hexdigest(configured)
        )
      end
    end
  end
end
