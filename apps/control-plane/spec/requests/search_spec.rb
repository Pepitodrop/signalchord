require "rails_helper"

RSpec.describe "search", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user:, role: "viewer") }
  let!(:token) { ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("viewer")).last }
  let(:headers) { { "Authorization" => "Bearer #{token}" } }

  def stub_opensearch(hits: [])
    fake_response = instance_double(Net::HTTPOK, body: { hits: { hits: hits } }.to_json)
    allow(fake_response).to receive(:is_a?).with(Net::HTTPSuccess).and_return(true)
    allow(Net::HTTP).to receive(:start).and_yield(instance_double(Net::HTTP, request: fake_response))
    fake_response
  end

  it "forces the caller's own tenant_id into every OpenSearch query, ignoring any client-supplied value" do
    captured_bodies = []
    allow_any_instance_of(Net::HTTP::Post).to receive(:body=) { |post, body| captured_bodies << body }
    stub_opensearch

    get "/api/v1/search", params: { q: "acme", tenant_id: "some-other-org-id" }, headers: headers

    expect(response).to have_http_status(:ok)
    expect(captured_bodies).not_to be_empty
    captured_bodies.each do |body|
      filters = JSON.parse(body).dig("query", "bool", "filter")
      expect(filters).to include({ "term" => { "tenant_id" => organization.id } })
    end
  end

  it "returns 400 (not a 500) for a missing/blank query" do
    # params.require(:q) treats a blank string the same as a missing key, so
    # this never reaches the controller's own query.blank? branch — that
    # branch is unreachable today, a pre-existing quirk unrelated to this
    # feature's scope.
    get "/api/v1/search", params: { q: "" }, headers: headers

    expect(response).to have_http_status(:bad_request)
  end

  it "returns empty results (not a 500) when OpenSearch is unreachable" do
    allow(Net::HTTP).to receive(:start).and_raise(Errno::ECONNREFUSED)

    get "/api/v1/search", params: { q: "acme" }, headers: headers

    expect(response).to have_http_status(:ok)
    expect(JSON.parse(response.body)["results"]).to eq([])
  end
end
