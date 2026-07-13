class PolicyVersion < ApplicationRecord
  belongs_to :policy

  validates :version_number, presence: true, uniqueness: { scope: :policy_id }
  validates :engine, inclusion: { in: %w[velato fallback] }
  validates :source_bytes, length: { maximum: 128_000 }, allow_nil: true

  def source_size
    source_bytes&.bytesize || 0
  end
end
