require "rails_helper"

RSpec.describe "notification endpoints", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user:, role: "analyst") }
  let!(:token) { ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("analyst")).last }
  let(:headers) { { "Authorization" => "Bearer #{token}" } }

  it "creates and lists the caller's own endpoint" do
    post "/api/v1/notification_endpoints", params: { platform: "ios", token: "device-token-1" }, headers: headers
    expect(response).to have_http_status(:created)

    get "/api/v1/notification_endpoints", headers: headers
    expect(JSON.parse(response.body).map { |row| row.fetch("platform") }).to eq(["ios"])
  end

  it "never lists another member's endpoint, even within the same organization" do
    other_user = User.create!(email: "other-member@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: other_user, role: "analyst")
    _record, other_token = ApiToken.issue!(organization:, user: other_user, name: "test", scopes: Membership.scopes_for("analyst"))
    post "/api/v1/notification_endpoints", params: { platform: "android", token: "other-device" }, headers: { "Authorization" => "Bearer #{other_token}" }

    get "/api/v1/notification_endpoints", headers: headers
    expect(JSON.parse(response.body)).to eq([])
  end

  it "never lists another organization's endpoint" do
    other_org = Organization.create!(name: "Beta", slug: "beta")
    other_user = User.create!(email: "beta@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization: other_org, user: other_user, role: "analyst")
    _record, other_token = ApiToken.issue!(organization: other_org, user: other_user, name: "test", scopes: Membership.scopes_for("analyst"))
    post "/api/v1/notification_endpoints", params: { platform: "android", token: "beta-device" }, headers: { "Authorization" => "Bearer #{other_token}" }

    get "/api/v1/notification_endpoints", headers: headers
    expect(JSON.parse(response.body)).to eq([])
  end

  it "cannot destroy another member's endpoint by guessed id, even within the same organization" do
    other_user = User.create!(email: "other-member@example.com", password: "correct-horse-battery-staple")
    Membership.create!(organization:, user: other_user, role: "analyst")
    _record, other_token = ApiToken.issue!(organization:, user: other_user, name: "test", scopes: Membership.scopes_for("analyst"))
    post "/api/v1/notification_endpoints", params: { platform: "android", token: "other-device" }, headers: { "Authorization" => "Bearer #{other_token}" }
    other_endpoint_id = JSON.parse(response.body)["id"]

    delete "/api/v1/notification_endpoints/#{other_endpoint_id}", headers: headers

    expect(response).to have_http_status(:not_found)
    expect(NotificationEndpoint.find(other_endpoint_id).enabled).to be(true)
  end
end
