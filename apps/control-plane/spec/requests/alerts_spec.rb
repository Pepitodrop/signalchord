require "rails_helper"

RSpec.describe "GET /api/v1/alerts", type: :request do
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
  let!(:policy) { Policy.create!(organization:, name: "Watchlist Novelty") }

  it "sorts by prioritization score (alert_score) descending, severity as tiebreaker" do
    low = organization.alerts.create!(stable_id: "low", title: "Low", alert_score: 20, severity_code: 1)
    high = organization.alerts.create!(stable_id: "high", title: "High", alert_score: 90, severity_code: 5)
    mid_a = organization.alerts.create!(stable_id: "mid-a", title: "Mid A", alert_score: 50, severity_code: 7)
    mid_b = organization.alerts.create!(stable_id: "mid-b", title: "Mid B", alert_score: 50, severity_code: 3)

    get "/api/v1/alerts", headers: auth_headers

    ids = JSON.parse(response.body).map { |a| a.fetch("id") }
    expect(ids).to eq([high.id, mid_a.id, mid_b.id, low.id])
  end

  it "includes the resolved policy_name when policy_id is present" do
    alert = organization.alerts.create!(stable_id: "linked", title: "Linked", alert_score: 50, severity_code: 3, policy:)

    get "/api/v1/alerts", headers: auth_headers

    body = JSON.parse(response.body).find { |a| a.fetch("id") == alert.id }
    expect(body["policy_name"]).to eq("Watchlist Novelty")
  end

  it "reports policy_name as nil when the alert has no policy" do
    alert = organization.alerts.create!(stable_id: "unlinked", title: "Unlinked", alert_score: 50, severity_code: 3)

    get "/api/v1/alerts", headers: auth_headers

    body = JSON.parse(response.body).find { |a| a.fetch("id") == alert.id }
    expect(body["policy_name"]).to be_nil
  end

  it "filters to unread only when unread=true" do
    unread = organization.alerts.create!(stable_id: "unread", title: "Unread", alert_score: 50, severity_code: 3)
    organization.alerts.create!(stable_id: "read", title: "Read", alert_score: 50, severity_code: 3, read_at: Time.current)

    get "/api/v1/alerts", params: { unread: "true" }, headers: auth_headers

    ids = JSON.parse(response.body).map { |a| a.fetch("id") }
    expect(ids).to eq([unread.id])
  end

  it "does not N+1 when serializing policy_name across many alerts" do
    5.times { |i| organization.alerts.create!(stable_id: "alert-#{i}", title: "Alert #{i}", alert_score: 50, severity_code: 3, policy:) }

    queries = []
    subscriber = ActiveSupport::Notifications.subscribe("sql.active_record") do |*, payload|
      queries << payload[:sql] unless payload[:name] == "SCHEMA"
    end
    begin
      get "/api/v1/alerts", headers: auth_headers
    ensure
      ActiveSupport::Notifications.unsubscribe(subscriber)
    end

    policy_queries = queries.select { |sql| sql.include?("FROM \"policies\"") || sql.include?("FROM policies") }
    expect(policy_queries.size).to be <= 1
  end
end
