require "rails_helper"

RSpec.describe "governance requests", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "alpha@example.com", password: "correct-horse-battery-staple", display_name: "Alpha Admin") }
  let!(:membership) { Membership.create!(organization:, user:, role: "admin") }
  let!(:token_record_and_plaintext) { ApiToken.issue!(organization:, user:, name: "test", scopes: ["*"]) }
  let(:token) { token_record_and_plaintext.last }
  let(:auth_headers) { { "Authorization" => "Bearer #{token}" } }
  let!(:source) do
    organization.sources.create!(
      name: "Alpha feed",
      endpoint: "https://alpha.example/feed",
      adapter: "rss",
      rights_status: "approved",
      raw_retention_days: 30,
      policy_metadata: approved_source_metadata,
      enabled: true
    )
  end

  def approved_source_metadata
    {
      "owner" => "news-ops",
      "legal_basis" => "contract",
      "permitted_uses" => ["analysis", "alerts"],
      "attribution" => "Alpha News",
      "terms_status" => "approved",
      "geography" => ["US"],
      "retention_days" => 30,
      "deletion_obligations" => ["delete_raw_and_derived_on_request"]
    }
  end

  it "rejects enabled sources without a complete approved inventory record" do
    post "/api/v1/sources",
         params: {
           source: {
             name: "Incomplete feed",
             endpoint: "https://incomplete.example/feed",
             adapter: "rss",
             rights_status: "approved",
             enabled: true,
             raw_retention_days: 30,
             policy_metadata: { owner: "news-ops" }
           }
         },
         headers: auth_headers

    expect(response).to have_http_status(:unprocessable_entity)
    body = JSON.parse(response.body)
    expect(body.dig("details", "policy_metadata").join).to include("missing required production inventory fields")
  end

  it "creates an authenticated tenant export snapshot without leaking token digests" do
    organization.alerts.create!(stable_id: "alert-1", title: "Alert", alert_score: 80, severity_code: 5)

    post "/api/v1/governance_requests",
         params: { governance_request: { request_type: "tenant_export", parameters: { reason: "subject_access" } } },
         headers: auth_headers.merge("Idempotency-Key" => "export-1")

    expect(response).to have_http_status(:created)
    body = JSON.parse(response.body)
    expect(body.fetch("status")).to eq("completed")
    expect(body.dig("result", "sources").map { |item| item.fetch("id") }).to include(source.id)
    expect(body.to_json).not_to include("token_digest")
    expect(organization.audit_events.where(action: "governance_request.created").count).to eq(1)
  end

  it "is idempotent for tenant deletion and records a lifecycle event once" do
    organization.alerts.create!(stable_id: "alert-1", title: "Alert", alert_score: 80, severity_code: 5)

    2.times do
      post "/api/v1/governance_requests",
           params: { governance_request: { request_type: "tenant_deletion", parameters: { reason: "customer_request" } } },
           headers: auth_headers.merge("Idempotency-Key" => "delete-1")
    end

    expect(response).to have_http_status(:ok)
    expect(organization.governance_requests.where(request_type: "tenant_deletion").count).to eq(1)
    expect(source.reload.enabled).to be(false)
    expect(organization.alerts.first.reload).to be_suppressed
    expect(OutboxEvent.where(event_type: "tenant.deletion.requested.v1").count).to eq(1)
  end

  it "disables a source takedown and emits search and graph propagation events" do
    post "/api/v1/governance_requests",
         params: { governance_request: { request_type: "source_takedown", source_id: source.id, parameters: { reason: "contract_expired" } } },
         headers: auth_headers.merge("Idempotency-Key" => "takedown-1")

    expect(response).to have_http_status(:created)
    expect(source.reload.enabled).to be(false)
    expect(source.rights_status).to eq("denied")
    expect(source.policy_metadata.fetch("takedown_reason")).to eq("contract_expired")
    expect(OutboxEvent.where(event_type: "source.takedown.requested.v1").count).to eq(1)
    graph_event = OutboxEvent.find_by!(event_type: "graph.mutation-requested.v1")
    expect(graph_event.payload.fetch("mutation_type")).to eq("mark_source_takedown")
    expect(graph_event.payload.fetch("stable_id")).to eq(source.id)
  end
end
