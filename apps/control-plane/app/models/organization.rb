class Organization < ApplicationRecord
  has_many :memberships, dependent: :destroy
  has_many :users, through: :memberships
  has_many :api_tokens, dependent: :destroy
  has_many :sources, dependent: :destroy
  has_many :watchlists, dependent: :destroy
  has_many :policies, dependent: :destroy
  has_many :alerts, dependent: :destroy
  has_many :investigations, dependent: :destroy
  has_many :audit_events, dependent: :destroy

  validates :name, presence: true, length: { maximum: 200 }
  validates :slug, presence: true, uniqueness: true, format: { with: /\A[a-z0-9][a-z0-9-]*\z/ }
end
