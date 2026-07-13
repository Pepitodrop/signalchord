organization = Organization.find_or_initialize_by(slug: "demo")
organization.id ||= "00000000-0000-4000-8000-000000000001"
organization.name = "SignalChord Demo"
organization.save!

user = User.find_or_initialize_by(email: "analyst@signalchord.local")
user.id ||= "00000000-0000-4000-8000-000000000002"
user.display_name = "Demo Analyst"
user.password = ENV.fetch("SIGNALCHORD_DEMO_PASSWORD", "signalchord-demo-password") if user.new_record?
user.save!

Membership.find_or_create_by!(organization:, user:) { |record| record.role = "owner" }
ApiToken.find_or_create_by!(token_digest: ApiToken.digest("signalchord-dev-token")) do |record|
  record.organization = organization
  record.user = user
  record.name = "Local development"
  record.scopes = ["*"]
end

source = organization.sources.find_or_initialize_by(endpoint: "http://sample-source/feed.xml")
source.id ||= "00000000-0000-4000-8000-000000000101"
source.assign_attributes(
  name: "SignalChord Fixture Feed",
  adapter: "rss",
  rights_status: "approved",
  enabled: true,
  policy_metadata: { fixture: true, license: "repository-owned" }
)
source.save!

watchlist = Watchlist.find_or_initialize_by(organization:, name: "Technology companies")
watchlist.id ||= "00000000-0000-4000-8000-000000000201"
watchlist.save!
WatchlistItem.find_or_create_by!(watchlist:, target_stable_id: "company:acme") do |record|
  record.target_kind = "entity"
  record.relevance_weight = 1
end

policy = Policy.find_or_initialize_by(organization:, name: "Default watchlist novelty")
policy.id ||= "00000000-0000-4000-8000-000000000301"
policy.active = true
policy.save!
PolicyVersion.find_or_create_by!(policy:, version_number: 1) do |record|
  record.id = "00000000-0000-4000-8000-000000000302"
  record.engine = "velato"
  record.status = "active"
  record.source_sha256 = "203c4ded7e45fcd2ed614323dacfc6f480d71f1d165e785041461140baf62bea"
  midi_path = Rails.root.join("..", "..", "velato", "programs", "default-watchlist-novelty-v1.mid")
  record.source_bytes = File.binread(midi_path) if File.exist?(midi_path)
end
