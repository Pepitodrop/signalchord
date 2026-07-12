class OutboxEvent < ApplicationRecord
  belongs_to :organization, foreign_key: :tenant_id

  validates :tenant_id, :topic, :partition_key, :event_type, :correlation_id, :occurred_at, presence: true
  scope :pending, -> { where(published_at: nil).order(:created_at) }

  def self.enqueue!(organization:, topic:, partition_key:, event_type:, payload:, correlation_id: SecureRandom.uuid, causation_id: nil)
    create!(
      organization:,
      topic:,
      partition_key:,
      event_type:,
      schema_version: 1,
      payload:,
      correlation_id:,
      causation_id:,
      occurred_at: Time.current
    )
  end
end
