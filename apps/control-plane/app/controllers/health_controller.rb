class HealthController < ActionController::API
  def show
    ActiveRecord::Base.connection.select_value("SELECT 1")
    render json: { status: "ok", version: ENV.fetch("SIGNALCHORD_VERSION", "1.0.0") }
  rescue StandardError => error
    render json: { status: "error", error: error.class.name }, status: :service_unavailable
  end
end
