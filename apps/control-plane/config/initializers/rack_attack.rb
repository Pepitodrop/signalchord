class Rack::Attack
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
end
Rails.application.config.middleware.use Rack::Attack
