class Policy < ApplicationRecord
  belongs_to :organization
  has_many :policy_versions, dependent: :destroy
  validates :name, presence: true
end
