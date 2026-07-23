require "rails_helper"

RSpec.describe "product operations readiness", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:other_organization) { Organization.create!(name: "Beta", slug: "beta") }
  let!(:owner) { User.create!(email: "owner@example.com", password: "correct-horse-battery-staple", display_name: "Owner") }
  let!(:analyst) { User.create!(email: "analyst@example.com", password: "correct-horse-battery-staple", display_name: "Analyst") }
  let!(:other_user) { User.create!(email: "beta@example.com", password: "correct-horse-battery-staple", display_name: "Beta") }
  let!(:owner_membership) { Membership.create!(organization:, user: owner, role: "owner") }
  let!(:analyst_membership) { Membership.create!(organization:, user: analyst, role: "analyst") }
  let!(:other_membership) { Membership.create!(organization: other_organization, user: other_user, role: "owner") }
  let!(:usage_limit) { organization.create_usage_limit!(billing_state: "active", source_limit: 1, watchlist_limit: 1, notification_endpoint_limit: 1) }
  let!(:owner_token_record_and_plaintext) { ApiToken.issue!(organization:, user: owner, name: "owner", scopes: ["*"]) }
  let!(:analyst_token_record_and_plaintext) { ApiToken.issue!(organization:, user: analyst, name: "analyst", scopes: %w[api:read api:write]) }
  let!(:other_token_record_and_plaintext) { ApiToken.issue!(organization: other_organization, user: other_user, name: "beta", scopes: ["*"]) }
  let(:owner_token) { owner_token_record_and_plaintext.last }
  let(:analyst_token) { analyst_token_record_and_plaintext.last }
  let(:other_token) { other_token_record_and_plaintext.last }
  let(:owner_headers) { { "Authorization" => "Bearer #{owner_token}" } }
  let(:analyst_headers) { { "Authorization" => "Bearer #{analyst_token}" } }
  let(:other_headers) { { "Authorization" => "Bearer #{other_token}" } }

  it "invites and accepts a tenant member without manual database setup" do
    post "/api/v1/invitations",
         params: { email: "new-user@example.com", role: "reviewer" },
         headers: owner_headers

    expect(response).to have_http_status(:created)
    body = JSON.parse(response.body)
    invitation_token = body.fetch("invitation_token")
    expect(invitation_token).to start_with("sc_inv_")
    expect(body.to_json).not_to include("token_digest")

    post "/api/v1/invitations/accept",
         params: { invitation_token:, password: "new-correct-horse-battery-staple", display_name: "New Reviewer" }

    expect(response).to have_http_status(:created)
    accepted = JSON.parse(response.body)
    expect(accepted.fetch("organization").fetch("id")).to eq(organization.id)
    expect(accepted.fetch("role")).to eq("reviewer")
    expect(accepted.fetch("access_token")).to start_with("sc_")
    expect(organization.memberships.joins(:user).find_by!(users: { email: "new-user@example.com" }).role).to eq("reviewer")
    expect(organization.audit_events.pluck(:action)).to include("invitation.created", "invitation.accepted")

    post "/api/v1/invitations/accept",
         params: { invitation_token:, password: "new-correct-horse-battery-staple" }
    expect(response).to have_http_status(:unauthorized)
  end

  it "prevents non-admins and other tenants from managing invitations" do
    post "/api/v1/invitations",
         params: { email: "blocked@example.com", role: "reviewer" },
         headers: analyst_headers

    expect(response).to have_http_status(:forbidden)

    invitation, _plaintext = Invitation.issue!(
      organization: other_organization,
      email: "beta-invite@example.com",
      role: "analyst",
      invited_by_user_id: other_user.id
    )

    delete "/api/v1/invitations/#{invitation.id}", headers: owner_headers
    expect(response).to have_http_status(:not_found)
    expect(invitation.reload.revoked_at).to be_nil
  end

  it "lists and revokes only the current user's tenant sessions" do
    get "/api/v1/sessions", headers: analyst_headers
    expect(response).to have_http_status(:ok)
    ids = JSON.parse(response.body).map { |session| session.fetch("id") }
    expect(ids).to include(analyst_token_record_and_plaintext.first.id)
    expect(ids).not_to include(owner_token_record_and_plaintext.first.id)

    delete "/api/v1/sessions/#{owner_token_record_and_plaintext.first.id}", headers: analyst_headers
    expect(response).to have_http_status(:not_found)

    delete "/api/v1/auth/session", headers: analyst_headers
    expect(response).to have_http_status(:no_content)
    expect(analyst_token_record_and_plaintext.first.reload.revoked_at).to be_present
  end

  it "suspends a membership, revokes its tokens, and blocks future login" do
    delete "/api/v1/memberships/#{analyst_membership.id}", headers: owner_headers

    expect(response).to have_http_status(:no_content)
    expect(analyst_membership.reload.disabled_at).to be_present
    expect(analyst_token_record_and_plaintext.first.reload.revoked_at).to be_present

    post "/api/v1/auth/session",
         params: { email: analyst.email, password: "correct-horse-battery-staple", organization_slug: organization.slug }
    expect(response).to have_http_status(:unauthorized)
    expect(organization.audit_events.where(action: "membership.suspended").count).to eq(1)
  end

  it "prevents removing the last enabled owner" do
    delete "/api/v1/memberships/#{owner_membership.id}", headers: owner_headers
    expect(response).to have_http_status(:forbidden)
    expect(owner_membership.reload.disabled_at).to be_nil
  end

  it "prevents disabling the last enabled owner through membership update" do
    patch "/api/v1/memberships/#{owner_membership.id}",
          params: { membership: { disabled: true } },
          headers: owner_headers

    expect(response).to have_http_status(:forbidden)
    expect(owner_membership.reload.disabled_at).to be_nil
  end

  it "enforces tenant-local quota and billing write gates" do
    organization.sources.create!(
      name: "Alpha feed",
      endpoint: "https://alpha.example/feed",
      adapter: "rss",
      rights_status: "approved"
    )

    post "/api/v1/sources",
         params: { source: { name: "Second feed", endpoint: "https://second.example/feed", adapter: "rss", rights_status: "approved" } },
         headers: owner_headers
    expect(response).to have_http_status(:forbidden)

    patch "/api/v1/usage_limit",
          params: { usage_limit: { billing_state: "past_due", source_limit: 5 } },
          headers: owner_headers
    expect(response).to have_http_status(:ok)
    # billing_state is no longer client-mass-assignable (Blocker #7) — the
    # PATCH above only takes effect on source_limit. Confirm that, then set
    # the writability gate directly at the model layer, the way a real
    # billing system would.
    expect(usage_limit.reload.billing_state).to eq("active")
    usage_limit.update!(billing_state: "past_due")

    post "/api/v1/watchlists",
         params: { watchlist: { name: "Blocked watchlist" } },
         headers: owner_headers
    expect(response).to have_http_status(:payment_required)

    post "/api/v1/watchlists",
         params: { watchlist: { name: "Beta watchlist" } },
         headers: other_headers
    expect(response).to have_http_status(:created)
  end

  it "creates tenant-scoped support tickets and restricts status updates to admins" do
    post "/api/v1/support_tickets",
         params: { support_ticket: { subject: "Need help", category: "support", severity: "normal", description: "Onboarding question" } },
         headers: analyst_headers

    expect(response).to have_http_status(:created)
    ticket = SupportTicket.find(JSON.parse(response.body).fetch("id"))
    expect(ticket.organization_id).to eq(organization.id)
    expect(ticket.contact_email).to eq(analyst.email)

    patch "/api/v1/support_tickets/#{ticket.id}",
          params: { support_ticket: { status: "acknowledged" } },
          headers: analyst_headers
    expect(response).to have_http_status(:forbidden)

    patch "/api/v1/support_tickets/#{ticket.id}",
          params: { support_ticket: { status: "acknowledged" } },
          headers: owner_headers
    expect(response).to have_http_status(:ok)
    expect(ticket.reload.status).to eq("acknowledged")

    get "/api/v1/support_tickets/#{ticket.id}", headers: other_headers
    expect(response).to have_http_status(:not_found)
  end

  it "disables only the affected tenant notification endpoint on invalid provider token" do
    endpoint = NotificationEndpoint.register!(organization:, user: analyst, platform: "expo", token: "alpha-device")
    other_endpoint = NotificationEndpoint.register!(organization: other_organization, user: other_user, platform: "expo", token: "beta-device")
    delivery = organization.notification_deliveries.create!(notification_endpoint: endpoint, event_id: "event-1", alert_id: "alert-1", status: "sending")

    patch "/internal/v1/notification_targets/#{delivery.id}",
          params: { tenant_id: organization.id, status: "failed", last_error: "invalid_token: provider rejected device" },
          headers: { "X-SignalChord-Internal-Token" => "signalchord-local-internal" }

    expect(response).to have_http_status(:ok)
    expect(endpoint.reload.enabled).to be(false)
    expect(other_endpoint.reload.enabled).to be(true)
  end
end
