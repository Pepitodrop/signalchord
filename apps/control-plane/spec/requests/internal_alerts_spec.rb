require "rails_helper"

RSpec.describe "POST /internal/v1/alerts", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let(:internal_headers) { { "X-SignalChord-Internal-Token" => "signalchord-local-internal" } }
  let(:base_event) do
    {
      tenant_id: organization.id,
      correlation_id: SecureRandom.uuid,
      event_id: SecureRandom.uuid,
      payload: {
        alert_id: "stable-alert-1",
        title: "Signal detected",
        summary: "Something changed.",
        alert_score: 80,
        severity_code: 5,
        routing_code: 1,
        suppressed: false,
        evidence_ids: %w[ev-1],
        graph_path_ids: []
      }
    }
  end

  it "rejects a request with an invalid internal token" do
    post "/internal/v1/alerts", params: base_event, headers: { "X-SignalChord-Internal-Token" => "wrong" }
    expect(response).to have_http_status(:unauthorized)
  end

  it "enqueues zero AlertEmailNotificationJobs when no membership is opted in" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: false)

    expect {
      post "/internal/v1/alerts", params: base_event, headers: internal_headers
    }.not_to have_enqueued_job(AlertEmailNotificationJob)

    expect(response).to have_http_status(:created)
  end

  it "enqueues exactly one AlertEmailNotificationJob per opted-in membership" do
    opted_in_user = User.create!(email: "opted-in@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    opted_in_membership = Membership.create!(organization:, user: opted_in_user, role: "viewer", email_alerts_enabled: true)
    opted_out_user = User.create!(email: "opted-out@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user: opted_out_user, role: "viewer", email_alerts_enabled: false)

    post "/internal/v1/alerts", params: base_event, headers: internal_headers

    expect(response).to have_http_status(:created)
    alert = organization.alerts.find_by(stable_id: "stable-alert-1")
    enqueued = ActiveJob::Base.queue_adapter.enqueued_jobs.select { |job| job[:job] == AlertEmailNotificationJob }
    expect(enqueued.size).to eq(1)
    expect(enqueued.first[:args]).to eq([alert.id, opted_in_membership.id])
  end

  it "does not enqueue an email job (or push notification) for a suppressed alert" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: true)
    suppressed_event = base_event.deep_merge(payload: { suppressed: true })

    expect {
      post "/internal/v1/alerts", params: suppressed_event, headers: internal_headers
    }.not_to have_enqueued_job(AlertEmailNotificationJob)

    expect(organization.alerts.find_by(stable_id: "stable-alert-1")).to be_suppressed
  end

  it "never re-enqueues on a repeated create call with the same stable_id (idempotent)" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: true)

    post "/internal/v1/alerts", params: base_event, headers: internal_headers
    expect(response).to have_http_status(:created)

    expect {
      post "/internal/v1/alerts", params: base_event.deep_merge(event_id: SecureRandom.uuid), headers: internal_headers
    }.not_to have_enqueued_job(AlertEmailNotificationJob)

    expect(response).to have_http_status(:ok)
    expect(organization.alerts.where(stable_id: "stable-alert-1").count).to eq(1)
  end

  it "rolls back alert.save! if the push-notification OutboxEvent.enqueue! raises" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: true)
    allow(OutboxEvent).to receive(:enqueue!).and_raise(ActiveRecord::StatementInvalid, "connection blip")

    expect {
      post "/internal/v1/alerts", params: base_event, headers: internal_headers
    }.to raise_error(ActiveRecord::StatementInvalid)

    expect(organization.alerts.find_by(stable_id: "stable-alert-1")).to be_nil
  end

  it "rolls back alert.save! if enqueueing an email job raises (e.g. Redis unavailable)" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer", email_alerts_enabled: true)
    allow(AlertEmailNotificationJob).to receive(:perform_later).and_raise(StandardError, "redis unavailable")

    expect {
      post "/internal/v1/alerts", params: base_event, headers: internal_headers
    }.to raise_error(StandardError, "redis unavailable")

    expect(organization.alerts.find_by(stable_id: "stable-alert-1")).to be_nil
  end

  it "no longer carries the dead trace_hash/instructions_executed keys in policy_trace" do
    user = User.create!(email: "member@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
    Membership.create!(organization:, user:, role: "viewer")
    policy = Policy.create!(organization:, name: "Watchlist Novelty")
    event_with_policy = base_event.deep_merge(payload: { policy_id: policy.id, trace_hash: "abc", instructions_executed: 12 })

    post "/internal/v1/alerts", params: event_with_policy, headers: internal_headers

    alert = organization.alerts.find_by(stable_id: "stable-alert-1")
    expect(alert.policy_trace.keys).not_to include("trace_hash", "instructions_executed")
  end
end
