class OutboxEvent < ApplicationRecord
  validates :tenant_id, :topic, :partition_key, :event_type, :correlation_id, :occurred_at, presence: true
  scope :pending, -> { where(published_at: nil).order(:created_at) }
end
