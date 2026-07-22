class AlertEmailDelivery < ApplicationRecord
  # Mirrors NotificationDelivery::STATUSES (notification_delivery.rb) while
  # adding "sending" for ambiguous SMTP outcomes and "skipped" for recipients
  # who are no longer eligible when the queued job actually executes.
  STATUSES = %w[pending sending delivered failed skipped].freeze

  belongs_to :organization
  belongs_to :alert
  belongs_to :membership

  validates :status, presence: true, inclusion: { in: STATUSES }
  validates :alert_id, uniqueness: { scope: :membership_id }
end