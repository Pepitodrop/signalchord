require "rails_helper"

RSpec.describe "entities", type: :request do
  let!(:organization) { Organization.create!(name: "Alpha", slug: "alpha") }
  let!(:user) { User.create!(email: "member@example.com", password: "correct-horse-battery-staple") }
  let!(:membership) { Membership.create!(organization:, user:, role: "viewer") }
  let!(:token) { ApiToken.issue!(organization:, user:, name: "test", scopes: Membership.scopes_for("viewer")).last }
  let(:headers) { { "Authorization" => "Bearer #{token}" } }

  # Isolation here is delegated to the downstream graph-query service, which
  # is never reachable from this sandbox — what's under test is that this
  # controller always forces its OWN tenant_id into the proxied request, so a
  # client can never override which org's graph gets queried.
  def stub_graph_query(body: '{"stable_id":"company:acme"}', status: 200)
    fake_response = instance_double(Net::HTTPResponse, body:, code: status.to_s)
    allow(fake_response).to receive(:[]).with("content-type").and_return("application/json")
    allow(Net::HTTP).to receive(:get_response).and_return(fake_response)
    fake_response
  end

  it "forces the caller's own tenant_id into the proxied entity lookup" do
    stub_graph_query

    get "/api/v1/entities/company:acme", headers: headers

    expect(Net::HTTP).to have_received(:get_response) do |uri|
      expect(URI.decode_www_form(uri.query).to_h["tenant_id"]).to eq(organization.id)
    end
    expect(response).to have_http_status(:ok)
  end

  it "ignores any client-supplied tenant_id and always uses the authenticated org" do
    stub_graph_query

    get "/api/v1/entities/company:acme", params: { tenant_id: "some-other-org-id" }, headers: headers

    expect(Net::HTTP).to have_received(:get_response) do |uri|
      expect(URI.decode_www_form(uri.query).to_h["tenant_id"]).to eq(organization.id)
    end
  end

  it "forces tenant_id on the timeline endpoint too" do
    stub_graph_query(body: '{"items":[]}')

    get "/api/v1/entities/company:acme/timeline", headers: headers

    expect(Net::HTTP).to have_received(:get_response) do |uri|
      expect(URI.decode_www_form(uri.query).to_h["tenant_id"]).to eq(organization.id)
    end
  end

  it "forces tenant_id on the graph endpoint too" do
    stub_graph_query(body: '{"nodes":[],"relationships":[]}')

    get "/api/v1/entities/company:acme/graph", headers: headers

    expect(Net::HTTP).to have_received(:get_response) do |uri|
      expect(URI.decode_www_form(uri.query).to_h["tenant_id"]).to eq(organization.id)
    end
  end

  it "returns 503, not a 500, when the graph-query service is unreachable" do
    allow(Net::HTTP).to receive(:get_response).and_raise(Errno::ECONNREFUSED)

    get "/api/v1/entities/company:acme", headers: headers

    expect(response).to have_http_status(:service_unavailable)
  end
end
