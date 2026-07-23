require "rails_helper"

# Zero coverage existed for this controller before this feature. It's the
# service-to-service token-introspection endpoint services/realtime-gateway's
# Go SSE gateway calls to authorize a stream connection — see
# services/realtime-gateway/main.go for the consumer.
RSpec.describe "GET /internal/v1/token", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current) }
  let!(:membership) { Membership.create!(organization:, user:, role: "analyst") }
  let!(:token) { ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("analyst")).last }
  let(:internal_secret) { ENV.fetch("CONTROL_PLANE_INTERNAL_TOKEN", "signalchord-local-internal") }
  let(:internal_headers) { { "X-SignalChord-Internal-Token" => internal_secret, "Authorization" => "Bearer #{token}" } }

  it "rejects a request missing the internal shared-secret header" do
    get "/internal/v1/token", headers: { "Authorization" => "Bearer #{token}" }

    expect(response).to have_http_status(:unauthorized)
  end

  it "rejects a request with the wrong internal shared-secret" do
    get "/internal/v1/token", headers: { "X-SignalChord-Internal-Token" => "wrong-secret", "Authorization" => "Bearer #{token}" }

    expect(response).to have_http_status(:unauthorized)
  end

  it "rejects an invalid bearer token even with a correct internal secret" do
    get "/internal/v1/token", headers: { "X-SignalChord-Internal-Token" => internal_secret, "Authorization" => "Bearer sc_not-a-real-token" }

    expect(response).to have_http_status(:unauthorized)
  end

  it "resolves a valid token to organization_id/user_id/scopes" do
    get "/internal/v1/token", headers: internal_headers

    expect(response).to have_http_status(:ok)
    body = JSON.parse(response.body)
    expect(body["organization_id"]).to eq(organization.id)
    expect(body["user_id"]).to eq(user.id)
    expect(body["scopes"]).to eq(Membership.scopes_for("analyst"))
  end

  it "returns a non-2xx status when the membership is disabled (Blocker #3 regression) — the Go consumer already treats any non-200 as a hard denial" do
    membership.update!(disabled_at: Time.current)

    get "/internal/v1/token", headers: internal_headers

    expect(response.status).not_to be_between(200, 299)
  end

  it "returns a non-2xx status when the user is disabled (Blocker #3 regression)" do
    user.update!(disabled_at: Time.current)

    get "/internal/v1/token", headers: internal_headers

    expect(response.status).not_to be_between(200, 299)
  end

  it "never treats a userless (service) token as disabled" do
    _record, service_token = ApiToken.issue!(organization:, name: "service token", scopes: ["api:read"])

    get "/internal/v1/token", headers: { "X-SignalChord-Internal-Token" => internal_secret, "Authorization" => "Bearer #{service_token}" }

    expect(response).to have_http_status(:ok)
  end
end
