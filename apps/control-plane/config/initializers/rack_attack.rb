class Rack::Attack
  # Without a configured store, Rack::Attack falls back to an in-process
  # memory cache — in any multi-replica deployment every pod tracks
  # independent counters, so the effective limit on every throttle below
  # becomes configured_limit * replica_count (Blocker #4). Reuses the same
  # REDIS_URL already wired for Sidekiq, no new infra.
  #
  # Fail-open by design: ActiveSupport::Cache::RedisCacheStore's default
  # error_handler swallows connection errors and returns nil rather than
  # raising, so a Redis outage means rate limiting silently stops enforcing
  # rather than 503-ing every request under /api/*. A network blip on a
  # shared dependency should never take down the whole API.
  cache.store = ActiveSupport::Cache::RedisCacheStore.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0"))

  blocklist("api/body_size") do |request|
    next false unless request.path.start_with?("/api/")

    max_bytes = ENV.fetch("API_MAX_BODY_BYTES", 1_048_576).to_i
    request.content_length.to_i > max_bytes
  end

  throttle("api/ip", limit: ENV.fetch("API_RATE_LIMIT", 600).to_i, period: 1.minute) do |request|
    request.ip if request.path.start_with?("/api/")
  end

  throttle("api/auth/ip", limit: ENV.fetch("AUTH_RATE_LIMIT", 30).to_i, period: 5.minutes) do |request|
    request.ip if request.post? && request.path == "/api/v1/auth/session"
  end

  throttle("api/signup/ip", limit: ENV.fetch("SIGNUP_RATE_LIMIT", 10).to_i, period: 1.hour) do |request|
    request.ip if request.post? && request.path == "/api/v1/signup"
  end

  throttle("api/email_verification/ip", limit: ENV.fetch("EMAIL_VERIFICATION_RATE_LIMIT", 20).to_i, period: 1.hour) do |request|
    request.ip if request.post? && request.path == "/api/v1/email_verifications"
  end

  throttle("api/email_verification_resend/ip", limit: ENV.fetch("EMAIL_VERIFICATION_RESEND_RATE_LIMIT", 5).to_i, period: 1.hour) do |request|
    request.ip if request.post? && request.path == "/api/v1/email_verifications/resend"
  end

  throttle("api/web_session/ip", limit: ENV.fetch("AUTH_RATE_LIMIT", 30).to_i, period: 5.minutes) do |request|
    request.ip if request.post? && request.path == "/api/v1/auth/web_session"
  end

  # This endpoint re-validates a raw email+password itself (decision 5 removed
  # the intermediate pending session), so it's a second full credential-check
  # surface and needs the same throttle shape as auth/session and web_session,
  # not just the general /api/* limit.
  throttle("api/organizations_create/ip", limit: ENV.fetch("AUTH_RATE_LIMIT", 30).to_i, period: 5.minutes) do |request|
    request.ip if request.post? && request.path == "/api/v1/organizations"
  end

  # Mints a session from a client-supplied token exactly like login/signup —
  # same abuse surface, same throttle shape as its sibling auth endpoints.
  throttle("api/invitations_accept/ip", limit: ENV.fetch("AUTH_RATE_LIMIT", 30).to_i, period: 5.minutes) do |request|
    request.ip if request.post? && request.path == "/api/v1/invitations/accept"
  end

  # The default responder leaks the exact configured limit and reset time via
  # RateLimit-Limit/RateLimit-Reset headers, letting an attacker calibrate a
  # request rate just under the threshold. Match the app's existing error
  # shape without those headers.
  self.throttled_responder = lambda do |_request|
    [429, { "Content-Type" => "application/json" }, [{ error: "rate_limited" }.to_json]]
  end
end
Rails.application.config.middleware.use Rack::Attack

# Throttle/blocklist hits are currently invisible — no subscriber existed
# anywhere before this. Same structured shape as
# ApplicationController#log_security_denial! so both denial paths land in
# the same log format.
ActiveSupport::Notifications.subscribe("throttle.rack_attack") do |_name, _start, _finish, _id, payload|
  request = payload[:request]
  Rails.logger.warn(
    {
      event: "security_denial",
      reason: "rate_limited",
      path: request.path,
      method: request.request_method,
      ip: request.ip,
      request_id: request.env["action_dispatch.request_id"]
    }.compact.to_json
  )
end

ActiveSupport::Notifications.subscribe("blocklist.rack_attack") do |_name, _start, _finish, _id, payload|
  request = payload[:request]
  Rails.logger.warn(
    {
      event: "security_denial",
      reason: "blocklisted",
      path: request.path,
      method: request.request_method,
      ip: request.ip,
      request_id: request.env["action_dispatch.request_id"]
    }.compact.to_json
  )
end
