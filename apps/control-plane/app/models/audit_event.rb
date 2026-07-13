class AuditEvent < ApplicationRecord
  belongs_to :organization
  validates :action, :target_type, :occurred_at, presence: true
end
