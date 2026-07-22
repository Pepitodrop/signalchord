class Watchlist < ApplicationRecord
  belongs_to :organization
  has_many :watchlist_items, dependent: :destroy
  validates :name, presence: true, length: { maximum: 200 }
  # allow_nil so ordinary (non-idempotent) creates, which never set this
  # column, don't get validated against each other — only two explicit,
  # equal, non-blank keys within the same org are a real collision.
  validates :idempotency_key, uniqueness: { scope: :organization_id }, allow_nil: true
end
