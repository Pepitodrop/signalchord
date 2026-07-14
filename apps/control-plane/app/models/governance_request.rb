class GovernanceRequest < ApplicationRecord
  TYPES = %w[tenant_export tenant_deletion source_takedown].freeze
  STATUSES = %w[accepted completed].freeze

  belongs_to :organization
  belongs_to :source, optional: true

  validates :request_type, :idempotency_key, :status, presence: true
  validates :request_type, inclusion: { in: TYPES }
  validates :status, inclusion: { in: STATUSES }
  validates :idempotency_key, uniqueness: { scope: :organization_id }
end
