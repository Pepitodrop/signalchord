class Alert < ApplicationRecord
  belongs_to :organization
  belongs_to :policy, optional: true
  validates :stable_id, :title, :severity_code, :alert_score, presence: true
  validates :stable_id, uniqueness: { scope: :organization_id }
  validates :alert_score, numericality: { only_integer: true, in: 0..100 }
  validates :severity_code, numericality: { only_integer: true, in: 0..9 }
end
