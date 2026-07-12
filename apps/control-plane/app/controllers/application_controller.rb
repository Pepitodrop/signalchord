class ApplicationController < ActionController::API
  class Forbidden < StandardError; end

  before_action :authenticate_api_token!

  rescue_from ActiveRecord::RecordNotFound, with: -> { render_error("not_found", :not_found) }
  rescue_from ActiveRecord::RecordInvalid, with: ->(error) {
    render json: { error: "validation_failed", details: error.record.errors.to_hash }, status: :unprocessable_entity
  }
  rescue_from ActionController::ParameterMissing, with: ->(error) {
    render json: { error: "invalid_request", detail: error.message }, status: :bad_request
  }
  rescue_from Forbidden, with: -> { render_error("forbidden", :forbidden) }

  private

  attr_reader :current_api_token

  def authenticate_api_token!
    plaintext = request.authorization.to_s.delete_prefix("Bearer ").presence
    @current_api_token = ApiToken.authenticate(plaintext)
    return render_error("unauthorized", :unauthorized) unless @current_api_token

    @current_api_token.touch(:last_used_at)
  end

  def current_organization
    @current_api_token.organization
  end

  def current_membership
    return unless @current_api_token.user_id

    @current_membership ||= Membership.find_by(
      organization_id: current_organization.id,
      user_id: @current_api_token.user_id
    )
  end

  def require_scope!(scope)
    raise Forbidden unless @current_api_token.allows?(scope)
  end

  def require_role!(*roles)
    raise Forbidden unless current_membership && roles.include?(current_membership.role)
  end

  def audit!(action:, target:, metadata: {})
    current_organization.audit_events.create!(
      actor_user_id: @current_api_token.user_id,
      action:,
      target_type: target.class.name,
      target_id: target.id,
      metadata:,
      request_id: request.request_id,
      occurred_at: Time.current
    )
  end

  def render_error(code, status)
    render json: { error: code, request_id: request.request_id }, status:
  end
end
