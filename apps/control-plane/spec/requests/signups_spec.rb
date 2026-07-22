require "rails_helper"

RSpec.describe "POST /api/v1/signup", type: :request do
  let(:valid_params) do
    { email: "new-user@example.com", password: "correct-horse-battery-staple", beta_access_code: "the-real-code" }
  end

  around do |example|
    previous = ENV["BETA_ACCESS_CODE"]
    ENV["BETA_ACCESS_CODE"] = "the-real-code"
    example.run
  ensure
    previous.nil? ? ENV.delete("BETA_ACCESS_CODE") : ENV["BETA_ACCESS_CODE"] = previous
  end

  it "creates an unverified user and sends a verification email" do
    expect {
      post "/api/v1/signup", params: valid_params
    }.to change(User, :count).by(1).and change(ActionMailer::Base.deliveries, :count).by(1)

    expect(response).to have_http_status(:created)
    user = User.find_by(email: "new-user@example.com")
    expect(user.email_verified?).to eq(false)
    expect(user.verification_email_sent_at).to be_present
  end

  it "rejects a missing beta access code" do
    post "/api/v1/signup", params: valid_params.except(:beta_access_code)
    expect(response).to have_http_status(:bad_request)
  end

  it "rejects an incorrect beta access code" do
    post "/api/v1/signup", params: valid_params.merge(beta_access_code: "wrong-code")
    expect(response).to have_http_status(:unauthorized)
    expect(User.exists?(email: "new-user@example.com")).to eq(false)
  end

  it "fails closed when BETA_ACCESS_CODE is not configured" do
    ENV.delete("BETA_ACCESS_CODE")
    post "/api/v1/signup", params: valid_params.merge(beta_access_code: "")
    expect(response).to have_http_status(:unauthorized)
  end

  it "rejects a duplicate email with a clean 422" do
    User.create!(email: "new-user@example.com", password: "some-other-password")
    post "/api/v1/signup", params: valid_params
    expect(response).to have_http_status(:unprocessable_entity)
  end

  it "returns a clean 422 (not a 500) on a simulated concurrent duplicate signup race" do
    # Simulate the TOCTOU race: Rails' own uniqueness validation passes, but
    # the DB unique index rejects the insert as RecordNotUnique, not
    # RecordInvalid, because another identical request already committed.
    allow(User).to receive(:create!).and_raise(
      ActiveRecord::RecordNotUnique.new("duplicate key value violates unique constraint")
    )

    post "/api/v1/signup", params: valid_params

    expect(response).to have_http_status(:unprocessable_entity)
    expect(JSON.parse(response.body)["error"]).to eq("validation_failed")
  end

  it "still returns 201 and keeps the created user if the verification mailer raises" do
    allow(OnboardingMailer).to receive(:verification_email).and_raise(Net::OpenTimeout, "smtp timed out")

    post "/api/v1/signup", params: valid_params

    expect(response).to have_http_status(:created)
    expect(User.exists?(email: "new-user@example.com")).to eq(true)
  end

  it "is throttled after the configured number of signup attempts from one IP" do
    # Rack::Attack throttle limits are read from ENV once at initializer load
    # time, not per-request, so this exercises the actual configured default
    # (SIGNUP_RATE_LIMIT, 10) rather than trying to override it at runtime.
    Rack::Attack.cache.store.clear
    begin
      10.times { |i| post "/api/v1/signup", params: valid_params.merge(email: "user#{i}@example.com") }
      post "/api/v1/signup", params: valid_params.merge(email: "user-over-limit@example.com")
      expect(response).to have_http_status(:too_many_requests)
    ensure
      Rack::Attack.cache.store.clear
    end
  end
end
