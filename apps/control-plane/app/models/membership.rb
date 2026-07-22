class Membership < ApplicationRecord
  ROLES = %w[owner admin analyst reviewer viewer].freeze

  belongs_to :organization
  belongs_to :user
  validates :role, inclusion: { in: ROLES }
  validates :user_id, uniqueness: { scope: :organization_id }

  scope :enabled, -> { where(disabled_at: nil) }

  def self.scopes_for(role)
    case role
    when "owner", "admin" then ["*"]
    when "analyst", "reviewer" then %w[api:read api:write]
    else ["api:read"]
    end
  end

  def disabled?
    disabled_at.present?
  end
end
