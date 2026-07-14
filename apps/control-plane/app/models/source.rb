class Source < ApplicationRecord
  ADAPTERS = %w[rss atom webhook licensed_adapter].freeze
  RIGHTS = %w[pending_review approved denied].freeze
  REQUIRED_APPROVAL_METADATA = %w[
    owner
    legal_basis
    permitted_uses
    attribution
    terms_status
    geography
    retention_days
    deletion_obligations
  ].freeze

  belongs_to :organization
  has_many :governance_requests, dependent: :nullify
  validates :name, :endpoint, :adapter, :rights_status, presence: true
  validates :adapter, inclusion: { in: ADAPTERS }
  validates :rights_status, inclusion: { in: RIGHTS }
  validates :requests_per_minute, numericality: { only_integer: true, greater_than: 0, less_than_or_equal_to: 600 }
  validates :raw_retention_days, numericality: { only_integer: true, greater_than_or_equal_to: 0, less_than_or_equal_to: 3650 }
  validate :approved_before_enabled
  validate :complete_inventory_before_enablement

  after_commit :publish_registration_event, on: %i[create update]

  private

  def approved_before_enabled
    errors.add(:enabled, "requires approved rights") if enabled? && rights_status != "approved"
  end

  def complete_inventory_before_enablement
    return unless enabled?

    missing = REQUIRED_APPROVAL_METADATA.select { |key| metadata_value(key).blank? }
    errors.add(:policy_metadata, "missing required production inventory fields: #{missing.join(', ')}") if missing.any?
    if metadata_value("retention_days").present? && metadata_value("retention_days").to_i != raw_retention_days
      errors.add(:policy_metadata, "retention_days must match raw_retention_days")
    end
  end

  def metadata_value(key)
    policy_metadata[key] || policy_metadata[key.to_sym]
  end

  def publish_registration_event
    OutboxEvent.enqueue!(
      organization:,
      topic: "source.registered.v1",
      partition_key: id,
      event_type: "source.registered.v1",
      payload: as_json(only: %i[id name endpoint adapter rights_status enabled requests_per_minute raw_retention_days policy_metadata])
    )
  end
end
