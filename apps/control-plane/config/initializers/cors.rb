Rails.application.config.middleware.insert_before 0, Rack::Cors do
  allow do
    origins(*ENV.fetch("WEB_ORIGINS", "http://localhost:5173").split(","))
    resource "/api/*", headers: :any, methods: %i[get post put patch delete options head], expose: ["X-Request-ID"]
  end
end
