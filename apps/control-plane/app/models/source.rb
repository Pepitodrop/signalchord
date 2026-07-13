class Source < ApplicationRecord
  ADAPTERS = %w[rss atom webhook licensed_adapter].freeze
  RIGHTS = %w[pending_review approved denied].freeze

  belongs_to :organization
  validates :name, :endpoint, :adapter, :rights_status, presence: true
  validates :adapter, inclusion: { in: ADAPTERS }
  validates :rights_status, inclusion: { in: RIGHTS }
  validates :requests_per_minute, numericality: { only_integer: true, greater_than: 0, less_than_or_equal_to: 600 }
  validates :raw_retention_days, numericality: { only_integer: true, greater_than_or_equal_to: 0, less_than_or_equal_to: 3650 }
  validate :approved_before_enabled

  after_commit :publish_registration_event, on: %i[create update]

  private

  def approved_before_enabled
    errors.add(:enabled, "requires approved rights") if enabled? && rights_status != "approved"
  end

  def publish_registration_event
    OutboxEvent.enqueue!(
      organization:,
      topic: "source.registered.v1",
      partition_key: id,
      event_type: "source.registered.v1",
      payload: as_json(only: %i[id name endpoint adapter rights_status enabled requests_per_minute raw_retention_days])
    )
  end
end
