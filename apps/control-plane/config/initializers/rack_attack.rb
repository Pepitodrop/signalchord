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
end
Rails.application.config.middleware.use Rack::Attack
