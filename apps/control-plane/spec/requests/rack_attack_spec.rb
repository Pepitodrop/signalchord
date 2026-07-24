require "rails_helper"

RSpec.describe "Rack::Attack", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }

  after { Rack::Attack.cache.store.clear }

  it "is configured with a Redis-backed cache store (Blocker #4)" do
    # Rack::Attack wraps an assigned ActiveSupport::Cache::RedisCacheStore in
    # its own StoreProxy adapter, so the class itself isn't a
    # RedisCacheStore — confirm it's the Redis-backed proxy, not the
    # in-process default (Rack::Attack::StoreProxy::MemoryStoreProxy).
    expect(Rack::Attack.cache.store.class.name).to include("Redis")
  end

  it "omits RateLimit-Limit/RateLimit-Reset headers on a throttled response (no calibration leak)" do
    # The throttle counts every matching request regardless of outcome, so an
    # intentionally-wrong beta code is fine here — only the throttle
    # trigger/header shape is under test, not signup success.
    Rack::Attack.cache.store.clear
    10.times { |i| post "/api/v1/signup", params: { email: "user#{i}@example.com", password: "correct-horse-battery-staple", beta_access_code: "wrong-code" } }
    post "/api/v1/signup", params: { email: "over-limit@example.com", password: "correct-horse-battery-staple", beta_access_code: "wrong-code" }

    expect(response).to have_http_status(:too_many_requests)
    expect(response.headers.keys).not_to include("RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset")
  end

  it "fails open (still serves the request) when Redis is unreachable, rather than 503ing the whole API" do
    unreachable_store = ActiveSupport::Cache::RedisCacheStore.new(url: "redis://localhost:1/0", connect_timeout: 0.2, error_handler: ->(method:, returning:, exception:) {})
    original_store = Rack::Attack.cache.store
    Rack::Attack.cache.store = unreachable_store
    begin
      get "/api/v1/me"
      expect(response).not_to have_http_status(:internal_server_error)
      expect(response).not_to have_http_status(:service_unavailable)
    ensure
      Rack::Attack.cache.store = original_store
    end
  end

  it "shares throttle counters across separate cache instances pointed at the same Redis (multi-replica consistency, Blocker #4)" do
    store_a = ActiveSupport::Cache::RedisCacheStore.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0"))
    store_b = ActiveSupport::Cache::RedisCacheStore.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0"))
    key = "test:cross-process-throttle-consistency"
    store_a.delete(key)

    store_a.increment(key, 1, expires_in: 60)
    store_b.increment(key, 1, expires_in: 60)

    # RedisCacheStore#increment writes via Redis's native INCR (a raw
    # integer), which #read can't reliably deserialize back — peek the
    # current value the same way increment itself does, by incrementing by 0.
    expect(store_a.increment(key, 0)).to eq(2)
    expect(store_b.increment(key, 0)).to eq(2)
  ensure
    store_a&.delete(key)
  end

  describe "security-denial logging" do
    it "logs a structured warning for an invalid token" do
      allow(Rails.logger).to receive(:warn)

      get "/api/v1/me", headers: { "Authorization" => "Bearer sc_not-a-real-token" }

      expect(Rails.logger).to have_received(:warn).with(a_string_matching(/"event":"security_denial".*"reason":"invalid_token"/))
    end

    it "logs a structured warning for a CSRF origin mismatch" do
      Membership.create!(organization:, user:, role: "admin")
      post "/api/v1/auth/web_session", params: { email: user.email, password: "correct-horse-battery-staple" }

      allow(Rails.logger).to receive(:warn)
      patch "/api/v1/me", params: { membership: { email_alerts_enabled: true } }, headers: { "Origin" => "https://attacker.example" }

      expect(Rails.logger).to have_received(:warn).with(a_string_matching(/"event":"security_denial".*"reason":"csrf_origin_mismatch"/))
    end

    it "logs a structured warning for a role/scope denial" do
      Membership.create!(organization:, user:, role: "viewer")
      _record, token = ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("viewer"))

      allow(Rails.logger).to receive(:warn)
      post "/api/v1/watchlists", params: { watchlist: { name: "blocked" } }, headers: { "Authorization" => "Bearer #{token}" }

      expect(Rails.logger).to have_received(:warn).with(a_string_matching(/"event":"security_denial".*"reason":"forbidden"/))
    end
  end
end
