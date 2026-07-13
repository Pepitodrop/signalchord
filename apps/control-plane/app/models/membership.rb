class Membership < ApplicationRecord
  ROLES = %w[owner admin analyst reviewer viewer].freeze

  belongs_to :organization
  belongs_to :user
  validates :role, inclusion: { in: ROLES }
  validates :user_id, uniqueness: { scope: :organization_id }
end
