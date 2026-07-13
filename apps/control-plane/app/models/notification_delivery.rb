class NotificationDelivery < ApplicationRecord
  STATUSES = %w[pending sending delivered failed].freeze

  belongs_to :organization
  belongs_to :notification_endpoint

  validates :event_id, :alert_id, :status, presence: true
  validates :status, inclusion: { in: STATUSES }
  validates :event_id, uniqueness: { scope: :notification_endpoint_id }
end
