require "rails_helper"

RSpec.describe "tenant isolation", type: :request do
  let!(:alpha) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:beta) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:alpha_user) { User.create!(email: "alpha@example.com", password: "correct-horse-battery-staple", display_name: "Alpha Analyst") }
  let!(:beta_user) { User.create!(email: "beta@example.com", password: "correct-horse-battery-staple", display_name: "Beta Analyst") }
  let!(:alpha_membership) { Membership.create!(organization: alpha, user: alpha_user, role: "admin") }
  let!(:beta_membership) { Membership.create!(organization: beta, user: beta_user, role: "admin") }
  let!(:token) do
    _record, plaintext = ApiToken.issue!(organization: alpha, name: "test", scopes: ["*"])
    plaintext
  end
  let(:auth_headers) { { "Authorization" => "Bearer #{token}" } }
  let!(:alpha_source) { alpha.sources.create!(name: "Alpha feed", endpoint: "https://alpha.example/feed", adapter: "rss", rights_status: "approved") }
  let!(:beta_source) { beta.sources.create!(name: "Beta feed", endpoint: "https://beta.example/feed", adapter: "rss", rights_status: "approved") }
  let!(:alpha_watchlist) { alpha.watchlists.create!(name: "Alpha watchlist") }
  let!(:beta_watchlist) { beta.watchlists.create!(name: "Beta watchlist") }
  let!(:alpha_policy) { alpha.policies.create!(name: "Alpha policy") }
  let!(:beta_policy) { beta.policies.create!(name: "Beta policy") }
  let!(:alpha_alert) { alpha.alerts.create!(stable_id: "alert-alpha", title: "Alpha alert", alert_score: 80, severity_code: 5) }
  let!(:beta_alert) { beta.alerts.create!(stable_id: "alert-beta", title: "Beta alert", alert_score: 80, severity_code: 5) }
  let!(:alpha_investigation) { alpha.investigations.create!(name: "Alpha investigation") }
  let!(:beta_investigation) { beta.investigations.create!(name: "Beta investigation") }

  it "never returns another tenant's source" do
    get "/api/v1/sources", headers: auth_headers
    ids = JSON.parse(response.body).map { |source| source.fetch("id") }
    expect(ids).to include(alpha_source.id)
    expect(ids).not_to include(beta_source.id)
  end

  it "does not read another tenant's resources by guessed id" do
    {
      "/api/v1/sources/#{beta_source.id}" => alpha_source.id,
      "/api/v1/watchlists/#{beta_watchlist.id}" => alpha_watchlist.id,
      "/api/v1/policies/#{beta_policy.id}" => alpha_policy.id,
      "/api/v1/alerts/#{beta_alert.id}" => alpha_alert.id,
      "/api/v1/investigations/#{beta_investigation.id}" => alpha_investigation.id
    }.each do |path, alpha_id|
      get path, headers: auth_headers
      expect(response).to have_http_status(:not_found), "#{path} leaked tenant data"
      expect(response.body).not_to include(alpha_id)
    end
  end

  it "does not modify another tenant's resources by guessed id" do
    patch "/api/v1/sources/#{beta_source.id}", params: { source: { name: "modified" } }, headers: auth_headers
    expect(response).to have_http_status(:not_found)
    expect(beta_source.reload.name).to eq("Beta feed")

    patch "/api/v1/alerts/#{beta_alert.id}", params: { alert: { review_status: "reviewed" } }, headers: auth_headers
    expect(response).to have_http_status(:not_found)
    expect(beta_alert.reload.review_status).to eq("unreviewed")
  end

  it "returns only the authenticated organization from organization endpoints" do
    get "/api/v1/organizations", headers: auth_headers
    ids = JSON.parse(response.body).map { |organization| organization.fetch("id") }
    expect(ids).to eq([alpha.id])
  end

  it "forces graph proxy tenant_id to the authenticated organization" do
    requested_uri = nil
    http_response = Struct.new(:body, :code) do
      def [](key) = key == "content-type" ? "application/json" : nil
    end.new("{}", "200")
    allow(Net::HTTP).to receive(:get_response) do |uri|
      requested_uri = uri
      http_response
    end

    get "/api/v1/entities/entity-1/graph", params: { tenant_id: beta.id, limit: 10 }, headers: auth_headers

    expect(response).to have_http_status(:ok)
    expect(Rack::Utils.parse_query(requested_uri.query)).to include("tenant_id" => alpha.id)
  end

  it "filters search queries to the authenticated tenant" do
    requests = []
    allow(Net::HTTP).to receive(:start) do |_host, _port, **_kwargs, &block|
      http = instance_double(Net::HTTP)
      allow(http).to receive(:request) do |request|
        requests << JSON.parse(request.body)
        instance_double(Net::HTTPSuccess, body: { hits: { hits: [] } }.to_json)
      end
      block.call(http)
    end

    get "/api/v1/search", params: { q: "risk", tenant_id: beta.id }, headers: auth_headers

    expect(response).to have_http_status(:ok)
    expect(requests).not_to be_empty
    requests.each do |body|
      expect(body.dig("query", "bool", "filter")).to include({ "term" => { "tenant_id" => alpha.id } })
    end
  end

  it "does not let one tenant update another tenant's notification delivery" do
    endpoint = NotificationEndpoint.register!(organization: beta, user: beta_user, platform: "expo", token: "beta-device")
    delivery = beta.notification_deliveries.create!(notification_endpoint: endpoint, event_id: "event-1", alert_id: beta_alert.id, status: "sending")

    patch "/internal/v1/notification_targets/#{delivery.id}",
          params: { tenant_id: alpha.id, status: "delivered" },
          headers: { "X-SignalChord-Internal-Token" => "signalchord-local-internal" }

    expect(response).to have_http_status(:not_found)
    expect(delivery.reload.status).to eq("sending")
  end

  it "updates notification deliveries only within the supplied tenant" do
    endpoint = NotificationEndpoint.register!(organization: alpha, user: alpha_user, platform: "expo", token: "alpha-device")
    delivery = alpha.notification_deliveries.create!(notification_endpoint: endpoint, event_id: "event-1", alert_id: alpha_alert.id, status: "sending")

    patch "/internal/v1/notification_targets/#{delivery.id}",
          params: { tenant_id: alpha.id, status: "delivered", provider_message_id: "provider-1" },
          headers: { "X-SignalChord-Internal-Token" => "signalchord-local-internal" }

    expect(response).to have_http_status(:ok)
    expect(delivery.reload.status).to eq("delivered")
  end

  it "rejects expired and revoked API tokens" do
    _expired_record, expired_plaintext = ApiToken.issue!(organization: alpha, name: "expired", scopes: ["*"], expires_at: 1.minute.ago)
    revoked_record, revoked_plaintext = ApiToken.issue!(organization: alpha, name: "revoked", scopes: ["*"])
    revoked_record.update!(revoked_at: Time.current)

    get "/api/v1/sources", headers: { "Authorization" => "Bearer #{expired_plaintext}" }
    expect(response).to have_http_status(:unauthorized)

    get "/api/v1/sources", headers: { "Authorization" => "Bearer #{revoked_plaintext}" }
    expect(response).to have_http_status(:unauthorized)
  end

  it "does not issue a session for a disabled user" do
    alpha_user.update!(disabled_at: Time.current)

    post "/api/v1/auth/session",
         params: { email: alpha_user.email, password: "correct-horse-battery-staple", organization_slug: alpha.slug }

    expect(response).to have_http_status(:unauthorized)
  end

  it "throttles repeated authentication attempts by IP" do
    Rack::Attack.cache.store.clear

    30.times do
      post "/api/v1/auth/session",
           params: { email: alpha_user.email, password: "wrong-password", organization_slug: alpha.slug }
      expect(response).to have_http_status(:unauthorized)
    end

    post "/api/v1/auth/session",
         params: { email: alpha_user.email, password: "wrong-password", organization_slug: alpha.slug }
    expect(response).to have_http_status(:too_many_requests)
  ensure
    Rack::Attack.cache.store.clear
  end

  it "sets secure response headers on API responses" do
    get "/api/v1/sources", headers: auth_headers

    expect(response.headers["X-Content-Type-Options"]).to eq("nosniff")
    expect(response.headers["X-Frame-Options"]).to eq("DENY")
    expect(response.headers["Referrer-Policy"]).to eq("no-referrer")
    expect(response.headers["Permissions-Policy"]).to include("camera=()")
  end

  it "rejects API requests over the configured body limit" do
    previous = ENV["API_MAX_BODY_BYTES"]
    ENV["API_MAX_BODY_BYTES"] = "10"
    begin
      post "/api/v1/sources",
           params: { source: { name: "large body", endpoint: "https://large.example/feed", adapter: "rss", rights_status: "approved" } }.to_json,
           headers: auth_headers.merge("CONTENT_TYPE" => "application/json", "CONTENT_LENGTH" => "1000")
    ensure
      previous.nil? ? ENV.delete("API_MAX_BODY_BYTES") : ENV["API_MAX_BODY_BYTES"] = previous
    end

    expect(response).to have_http_status(:forbidden)
  end
end
