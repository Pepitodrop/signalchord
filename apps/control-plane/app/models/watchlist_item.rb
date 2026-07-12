class WatchlistItem < ApplicationRecord
  KINDS = %w[entity topic search].freeze
  belongs_to :watchlist
  validates :target_kind, inclusion: { in: KINDS }
  validates :target_stable_id, presence: true, uniqueness: { scope: :watchlist_id }
  validates :relevance_weight, numericality: { greater_than_or_equal_to: 0, less_than_or_equal_to: 1 }
end
