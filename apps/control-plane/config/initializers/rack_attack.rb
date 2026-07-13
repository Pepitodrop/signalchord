class Rack::Attack
  throttle("api/ip", limit: ENV.fetch("API_RATE_LIMIT", 600).to_i, period: 1.minute) do |request|
    request.ip if request.path.start_with?("/api/")
  end
end
Rails.application.config.middleware.use Rack::Attack
