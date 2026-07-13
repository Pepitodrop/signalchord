class User < ApplicationRecord
  has_secure_password
  has_many :memberships, dependent: :destroy
  has_many :organizations, through: :memberships
  has_many :notification_endpoints, dependent: :destroy

  normalizes :email, with: ->(value) { value.strip.downcase }
  validates :email, presence: true, uniqueness: true
end
