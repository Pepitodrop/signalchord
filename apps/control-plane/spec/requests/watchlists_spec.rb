require "rails_helper"

RSpec.describe "POST /api/v1/watchlists", type: :request do
  let!(:organization) { Organization.create!(name: "Acme", slug: "acme") }
  let!(:user) do
    User.create!(email: "owner@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let!(:membership) { Membership.create!(organization:, user:, role: "owner") }
  let!(:token) do
    _record, plaintext = ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("owner"))
    plaintext
  end
  let(:auth_headers) { { "Authorization" => "Bearer #{token}" } }
  let(:valid_params) do
    { watchlist: { name: "Competitor moves", items: [{ target_kind: "entity", target_stable_id: "company:acme" }] } }
  end

  it "creates a watchlist with an item" do
    post "/api/v1/watchlists", params: valid_params, headers: auth_headers

    expect(response).to have_http_status(:created)
    body = JSON.parse(response.body)
    expect(body["name"]).to eq("Competitor moves")
    expect(body["items"].size).to eq(1)
    expect(body["items"].first["target_kind"]).to eq("entity")
  end

  it "returns understandable validation errors for an invalid target_kind" do
    post "/api/v1/watchlists",
         params: { watchlist: { name: "Bad", items: [{ target_kind: "not_a_real_kind", target_stable_id: "x" }] } },
         headers: auth_headers

    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)["error"]).to eq("validation_failed")
  end

  describe "idempotency (backward compatible)" do
    it "behaves exactly as before when no Idempotency-Key is sent — two calls create two watchlists" do
      post "/api/v1/watchlists", params: valid_params, headers: auth_headers
      post "/api/v1/watchlists", params: valid_params, headers: auth_headers

      expect(organization.watchlists.count).to eq(2)
    end

    it "returns the same watchlist on replay with the same Idempotency-Key, creating only one row" do
      headers = auth_headers.merge("Idempotency-Key" => "onboarding-watchlist-1")

      first_response = -> {
        post "/api/v1/watchlists", params: valid_params, headers:
        JSON.parse(response.body)
      }

      first = first_response.call
      expect(response).to have_http_status(:created)

      second = first_response.call
      expect(response).to have_http_status(:ok)

      expect(second["id"]).to eq(first["id"])
      expect(organization.watchlists.count).to eq(1)
    end

    it "responds with a clean conflict (not a 500) if a RecordNotUnique occurs and no matching row can be found" do
      # A genuine concurrent race (two requests both see "not found yet" and
      # both attempt to save) is hard to force deterministically in a
      # single-threaded request spec without fragile internals-mocking —
      # see organizations_concurrency_spec.rb for that style of test on the
      # higher-severity org-creation race. Here we verify the narrower,
      # still-important property: an unconditional RecordNotUnique never
      # surfaces as an unhandled 500, even in the case where the rescue's
      # own re-fetch finds nothing (rather than the more common case,
      # already covered above, where replaying a key finds the real row).
      headers = auth_headers.merge("Idempotency-Key" => "race-key")
      allow_any_instance_of(Watchlist).to receive(:save!).and_raise(
        ActiveRecord::RecordNotUnique.new("duplicate key value violates unique constraint")
      )

      post "/api/v1/watchlists", params: valid_params, headers:

      expect(response).to have_http_status(:conflict)
      expect(organization.watchlists.count).to eq(0)
    end

    it "scopes idempotency keys per organization — the same key in a different org does not collide" do
      other_organization = Organization.create!(name: "Other Co", slug: "other-co")
      other_user = User.create!(email: "other-owner@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
      Membership.create!(organization: other_organization, user: other_user, role: "owner")
      _record, other_plaintext = ApiToken.issue!(organization: other_organization, user: other_user, name: "test", scopes: Membership.scopes_for("owner"))

      shared_key_headers = { "Idempotency-Key" => "shared-across-orgs" }

      post "/api/v1/watchlists", params: valid_params, headers: auth_headers.merge(shared_key_headers)
      expect(response).to have_http_status(:created)

      post "/api/v1/watchlists", params: valid_params, headers: { "Authorization" => "Bearer #{other_plaintext}" }.merge(shared_key_headers)
      expect(response).to have_http_status(:created)

      expect(organization.watchlists.count).to eq(1)
      expect(other_organization.watchlists.count).to eq(1)
    end
  end
end
