class SupportTicket < ApplicationRecord
  CATEGORIES = %w[support incident security billing data_request].freeze
  SEVERITIES = %w[low normal high critical].freeze
  STATUSES = %w[open acknowledged waiting_on_customer resolved closed].freeze

  belongs_to :organization

  validates :subject, :contact_email, presence: true
  validates :category, inclusion: { in: CATEGORIES }
  validates :severity, inclusion: { in: SEVERITIES }
  validates :status, inclusion: { in: STATUSES }
end
