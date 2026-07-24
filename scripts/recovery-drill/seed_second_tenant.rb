# Recovery-drill fixture: a second, independent tenant, following
# db/seeds.rb's exact pattern (not editing that file) so the drill seeds 2+
# tenants per docs/specs/recovery-and-replay-hardening.md §24.9 step 3.
# Deterministic fixed UUIDs (a distinct 9000-series prefix from seeds.rb's
# 8000-series) so backup/restore row-count and checksum comparisons are
# exact and reproducible across drill runs.
#
# Invoked as: kubectl exec -i deployment/signalchord-control-plane --
#   bin/rails runner - < scripts/recovery-drill/seed_second_tenant.rb

organization = Organization.find_or_initialize_by(slug: "recovery-drill")
organization.id ||= "00000000-0000-4000-9000-000000000001"
organization.name = "Recovery Drill Tenant"
organization.save!

user = User.find_or_initialize_by(email: "drill@signalchord.local")
user.id ||= "00000000-0000-4000-9000-000000000002"
user.display_name = "Recovery Drill Operator"
user.password = ENV.fetch("SIGNALCHORD_DEMO_PASSWORD", "signalchord-demo-password") if user.new_record?
user.save!

Membership.find_or_create_by!(organization:, user:) { |record| record.role = "owner" }
ApiToken.find_or_create_by!(token_digest: ApiToken.digest("signalchord-recovery-drill-token")) do |record|
  record.organization = organization
  record.user = user
  record.name = "Recovery drill"
  record.scopes = ["*"]
end

source = organization.sources.find_or_initialize_by(endpoint: "http://sample-source/drill-feed.xml")
source.id ||= "00000000-0000-4000-9000-000000000101"
source.assign_attributes(
  name: "Recovery Drill Fixture Feed",
  adapter: "rss",
  rights_status: "approved",
  enabled: true,
  raw_retention_days: 30,
  policy_metadata: {
    owner: "news-ops",
    legal_basis: "first_party_fixture",
    permitted_uses: ["development_test", "synthetic_e2e"],
    attribution: "Synthetic SignalChord fixture",
    terms_status: "first_party_fixture",
    geography: ["local"],
    retention_days: 30,
    deletion_obligations: ["delete_raw_and_derived_on_request"],
    fixture: true,
    license: "repository-owned"
  }
)
source.save!

watchlist = Watchlist.find_or_initialize_by(organization:, name: "Recovery drill watchlist")
watchlist.id ||= "00000000-0000-4000-9000-000000000201"
watchlist.save!
WatchlistItem.find_or_create_by!(watchlist:, target_stable_id: "company:drillco") do |record|
  record.target_kind = "entity"
  record.relevance_weight = 1
end

policy = Policy.find_or_initialize_by(organization:, name: "Recovery drill policy")
policy.id ||= "00000000-0000-4000-9000-000000000301"
policy.active = true
policy.save!
PolicyVersion.find_or_create_by!(policy:, version_number: 1) do |record|
  record.id = "00000000-0000-4000-9000-000000000302"
  record.engine = "velato"
  record.status = "active"
  record.source_sha256 = "203c4ded7e45fcd2ed614323dacfc6f480d71f1d165e785041461140baf62bea"
  midi_path = Rails.root.join("..", "..", "velato", "programs", "default-watchlist-novelty-v1.mid")
  record.source_bytes = File.binread(midi_path) if File.exist?(midi_path)
end

puts "recovery-drill: seeded second tenant #{organization.id}"
