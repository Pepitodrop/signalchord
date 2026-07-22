require "rails_helper"

RSpec.describe "POST /api/v1/organizations", type: :request do
  let!(:verified_user) do
    User.create!(email: "founder@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)
  end
  let(:valid_params) { { email: verified_user.email, password: "correct-horse-battery-staple", name: "Acme Research" } }

  it "creates an organization and an owner membership, and returns a session cookie" do
    post "/api/v1/organizations", params: valid_params

    expect(response).to have_http_status(:created)
    body = JSON.parse(response.body)
    expect(body["name"]).to eq("Acme Research")
    expect(body["slug"]).to eq("acme-research")
    expect(body["role"]).to eq("owner")

    organization = Organization.find(body["id"])
    membership = Membership.find_by(organization:, user: verified_user)
    expect(membership.role).to eq("owner")
    expect(response.cookies[CookieSession::SESSION_COOKIE_NAME]).to be_present
  end

  it "rejects invalid credentials" do
    post "/api/v1/organizations", params: valid_params.merge(password: "wrong-password")
    expect(response).to have_http_status(:unauthorized)
    expect(Organization.exists?(slug: "acme-research")).to eq(false)
  end

  it "rejects an unverified user" do
    verified_user.update!(email_verified_at: nil)
    post "/api/v1/organizations", params: valid_params
    expect(response).to have_http_status(:forbidden)
  end

  it "auto-suffixes the slug on a collision instead of surfacing a validation error" do
    Organization.create!(name: "Acme Research (existing)", slug: "acme-research")

    post "/api/v1/organizations", params: valid_params

    expect(response).to have_http_status(:created)
    expect(JSON.parse(response.body)["slug"]).to eq("acme-research-2")
  end

  it "rejects a second workspace via this endpoint if the user already has one" do
    existing = Organization.create!(name: "Existing Co", slug: "existing-co")
    Membership.create!(organization: existing, user: verified_user, role: "owner")

    post "/api/v1/organizations", params: valid_params

    expect(response).to have_http_status(:unprocessable_entity)
    expect(Organization.exists?(slug: "acme-research")).to eq(false)
  end

  it "allows creating a workspace if the user's only membership was disabled (not a blocker)" do
    existing = Organization.create!(name: "Old Co", slug: "old-co")
    Membership.create!(organization: existing, user: verified_user, role: "owner", disabled_at: Time.current)

    post "/api/v1/organizations", params: valid_params

    expect(response).to have_http_status(:created)
  end

  it "returns a clean 409 (not a 500) on a simulated concurrent slug collision race" do
    # Same TOCTOU shape as signups_spec.rb's RecordNotUnique test: two
    # different users naming their workspace identically can both pass
    # unique_slug_for's pre-check before either commits, so the DB's real
    # unique index on organizations.slug is the actual backstop.
    allow(Organization).to receive(:create!).and_raise(
      ActiveRecord::RecordNotUnique.new("duplicate key value violates unique constraint")
    )

    post "/api/v1/organizations", params: valid_params

    expect(response).to have_http_status(:conflict)
    expect(JSON.parse(response.body)["error"]).to eq("slug_collision_retry")
  end

  it "is throttled after repeated attempts from one IP" do
    Rack::Attack.cache.store.clear
    begin
      30.times do
        post "/api/v1/organizations", params: valid_params.merge(password: "wrong-password")
        expect(response).to have_http_status(:unauthorized)
      end
      post "/api/v1/organizations", params: valid_params.merge(password: "wrong-password")
      expect(response).to have_http_status(:too_many_requests)
    ensure
      Rack::Attack.cache.store.clear
    end
  end
end
