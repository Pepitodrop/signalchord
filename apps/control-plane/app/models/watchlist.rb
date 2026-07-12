class Watchlist < ApplicationRecord
  belongs_to :organization
  has_many :watchlist_items, dependent: :destroy
  validates :name, presence: true, length: { maximum: 200 }
end
