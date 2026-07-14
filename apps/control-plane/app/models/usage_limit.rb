class UsageLimit < ApplicationRecord
  BILLING_STATES = %w[trialing active past_due suspended canceled].freeze
  WRITABLE_STATES = %w[trialing active].freeze

  belongs_to :organization

  validates :billing_state, inclusion: { in: BILLING_STATES }
  validates :source_limit, :watchlist_limit, :notification_endpoint_limit, :monthly_api_request_limit,
            numericality: { only_integer: true, greater_than_or_equal_to: 0 }

  def writable?
    WRITABLE_STATES.include?(billing_state)
  end
end
