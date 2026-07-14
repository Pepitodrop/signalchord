Rails.application.config.action_dispatch.default_headers.merge!(
  "X-Content-Type-Options" => "nosniff",
  "X-Frame-Options" => "DENY",
  "Referrer-Policy" => "no-referrer",
  "Permissions-Policy" => "camera=(), microphone=(), geolocation=()"
)
