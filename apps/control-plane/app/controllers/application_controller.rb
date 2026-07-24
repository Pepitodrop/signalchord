class ApplicationController < ActionController::API
  include CookieSession

  class Forbidden < StandardError; end

  before_action :authenticate_api_token!
  before_action :verify_same_origin!

  rescue_from ActiveRecord::RecordNotFound, with: -> { render_error("not_found", :not_found) }
  rescue_from ActiveRecord::RecordInvalid, with: ->(error) {
    render json: { error: "validation_failed", details: error.record.errors.to_hash }, status: :unprocessable_entity
  }
  rescue_from ActionController::ParameterMissing, with: ->(error) {
    render json: { error: "invalid_request", detail: error.message }, status: :bad_request
  }
  rescue_from Forbidden, with: -> {
    log_security_denial!(event: "forbidden")
    render_error("forbidden", :forbidden)
  }

  private

  attr_reader :current_api_token

  def authenticate_api_token!
    header_token = request.authorization.to_s.delete_prefix("Bearer ").presence
    if header_token
      @current_auth_source = :header
      @current_api_token = ApiToken.authenticate(header_token)
    else
      @current_auth_source = :cookie
      @current_api_token = ApiToken.authenticate(bearer_token_from_cookie)
    end
    unless @current_api_token
      log_security_denial!(event: "invalid_token")
      return render_error("unauthorized", :unauthorized)
    end
    if current_user_disabled_or_suspended?
      log_security_denial!(event: "disabled_account")
      return render_error("forbidden", :forbidden)
    end

    @current_api_token.touch(:last_used_at)
  end

  # CSRF: a header-based bearer token (mobile, scripts) is never automatically
  # attached by a browser, so it carries no CSRF risk and is skipped here.
  # A cookie IS automatically attached by the browser on every request to this
  # origin, so any mutating request that authenticated via cookie must also
  # prove it actually came from our own frontend. Requests that skip
  # authenticate_api_token! entirely (signup, organization creation, invitation
  # acceptance) never set @current_auth_source, so this is a no-op for them —
  # they take fresh credentials in the body, not an ambient cookie, so there is
  # nothing here for CSRF to exploit.
  def verify_same_origin!
    return unless @current_auth_source == :cookie
    return if request.get? || request.head?

    allowed_origins = ENV.fetch("WEB_ORIGINS", "http://localhost:5173").split(",").map(&:strip)
    origin = request.headers["Origin"]
    return if origin.present? && allowed_origins.include?(origin)

    log_security_denial!(event: "csrf_origin_mismatch")
    render_error("forbidden", :forbidden)
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
    raise Forbidden unless allowed_scopes.include?(scope) || allowed_scopes.include?("*")
  end

  # User-bound tokens: derive from the LIVE membership role, not the token's
  # issuance-time scopes snapshot — a role downgrade takes effect on the very
  # next request, matching how require_role! already re-reads the live role.
  # Tokens with no bound user (ApiToken#user is optional) have no membership
  # to consult, so they fall back to the token's own stored scopes.
  def allowed_scopes
    current_membership ? Membership.scopes_for(current_membership.role) : @current_api_token.scopes
  end

  def require_role!(*roles)
    raise Forbidden unless current_membership && roles.include?(current_membership.role)
  end

  def require_writable_account!
    return if current_organization.effective_usage_limit.writable?

    render_error("account_not_writable", :payment_required)
  end

  def enforce_usage_limit!(resource)
    limit = current_organization.effective_usage_limit
    current, maximum = case resource
                       when :sources then [current_organization.sources.count, limit.source_limit]
                       when :watchlists then [current_organization.watchlists.count, limit.watchlist_limit]
                       when :notification_endpoints then [current_organization.notification_endpoints.count, limit.notification_endpoint_limit]
                       else raise ArgumentError, "unknown usage limit resource: #{resource}"
                       end
    return if current < maximum

    raise Forbidden
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

  def current_user_disabled_or_suspended?
    @current_api_token&.user_or_membership_disabled?(membership: current_membership) || false
  end

  # event: short machine-readable reason (invalid_token, disabled_account,
  # csrf_origin_mismatch, forbidden). org_id/user_id are included only when
  # resolvable — many denials (invalid token, missing Origin) happen before
  # any org/user context exists.
  def log_security_denial!(event:)
    Rails.logger.warn(
      {
        event: "security_denial",
        reason: event,
        path: request.path,
        method: request.method,
        ip: request.remote_ip,
        request_id: request.request_id,
        org_id: @current_api_token&.organization_id,
        user_id: @current_api_token&.user_id
      }.compact.to_json
    )
  end
end
