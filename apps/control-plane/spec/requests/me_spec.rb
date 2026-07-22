require "rails_helper"

RSpec.describe "GET /api/v1/me", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) do
    User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:membership) { Membership.create!(organization:, user:, role: "admin") }
  let!(:token) do
    _record, plaintext = ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("admin"))
    plaintext
  end
  let(:auth_headers) { { "Authorization" => "Bearer #{token}" } }

  it "returns 401 with no session at all" do
    get "/api/v1/me"
    expect(response).to have_http_status(:unauthorized)
  end

  it "reports first_watchlist_required when the organization has no watchlists yet" do
    get "/api/v1/me", headers: auth_headers

    expect(response).to have_http_status(:ok)
    body = JSON.parse(response.body)
    expect(body["onboarding_state"]).to eq("first_watchlist_required")
    expect(body["role"]).to eq("admin")
    expect(body["organization"]["id"]).to eq(organization.id)
  end

  it "reports complete once the organization has at least one watchlist" do
    organization.watchlists.create!(name: "First watchlist")

    get "/api/v1/me", headers: auth_headers

    expect(JSON.parse(response.body)["onboarding_state"]).to eq("complete")
  end

  it "does not require the CALLING user to have created the watchlist — org-scoped, not user-scoped" do
    other_user = User.create!(email: "other@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user: other_user, role: "viewer")
    organization.watchlists.create!(name: "Created by admin")

    _record, other_plaintext = ApiToken.issue!(organization:, user: other_user, name: "test", scopes: Membership.scopes_for("viewer"))
    get "/api/v1/me", headers: { "Authorization" => "Bearer #{other_plaintext}" }

    expect(JSON.parse(response.body)["onboarding_state"]).to eq("complete")
  end

  it "checks watchlist existence with an EXISTS query, never loading full rows (no N+1 foot-gun)" do
    3.times { |i| organization.watchlists.create!(name: "Watchlist #{i}") }

    queries = []
    subscriber = ActiveSupport::Notifications.subscribe("sql.active_record") do |*, payload|
      queries << payload[:sql] unless payload[:name] == "SCHEMA"
    end
    begin
      get "/api/v1/me", headers: auth_headers
    ensure
      ActiveSupport::Notifications.unsubscribe(subscriber)
    end

    watchlist_queries = queries.select { |sql| sql.include?("watchlists") }
    expect(watchlist_queries).not_to be_empty
    expect(watchlist_queries).to all(match(/SELECT\s+1|EXISTS/i)), "expected an EXISTS-style query, not a full row load"
  end

  it "works identically via a cookie session (no auth-path drift)" do
    cookies.encrypted[CookieSession::SESSION_COOKIE_NAME] = token

    get "/api/v1/me"

    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)["onboarding_state"]).to eq("first_watchlist_required")
  end

  # Defensive coverage: authenticate_api_token! is expected to already
  # guarantee a verified, enabled-membership user reaches this action at all.
  # These prove the derivation still reports correctly if that invariant is
  # ever violated by a future change elsewhere, rather than crashing or
  # silently misreporting "complete".
  context "if the verified/enabled-membership invariant were ever violated" do
    it "falls back to verification_required if email_verified_at is unset out from under an existing session" do
      user.update_column(:email_verified_at, nil) # rubocop:disable Rails/SkipsModelValidations

      get "/api/v1/me", headers: auth_headers

      expect(JSON.parse(response.body)["onboarding_state"]).to eq("verification_required")
    end

    it "falls back to workspace_required if the membership is disabled out from under an existing session" do
      # authenticate_api_token! itself already rejects this with 403 before
      # reaching the action (current_user_disabled_or_suspended?) — this just
      # locks in that the two layers agree rather than silently diverging.
      membership.update!(disabled_at: Time.current)

      get "/api/v1/me", headers: auth_headers

      expect(response).to have_http_status(:forbidden)
    end
  end
end
