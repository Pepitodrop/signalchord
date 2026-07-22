class AlertEmailDelivery < ApplicationRecord
  # Mirrors NotificationDelivery::STATUSES (notification_delivery.rb) rather
  # than inventing a new shape. "sending" is the in-flight marker used to
  # detect a job that got far enough to attempt a send but never confirmed
  # the outcome — see AlertEmailNotificationJob for how that state is used
  # to avoid a possible duplicate send.
  STATUSES = %w[pending sending delivered failed].freeze

  belongs_to :organization
  belongs_to :alert
  belongs_to :membership

  validates :status, presence: true, inclusion: { in: STATUSES }
  validates :alert_id, uniqueness: { scope: :membership_id }
end
