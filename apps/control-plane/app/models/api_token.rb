require "digest"
require "securerandom"

class ApiToken < ApplicationRecord
  belongs_to :organization
  belongs_to :user, optional: true

  scope :active, -> { where(revoked_at: nil).where("expires_at IS NULL OR expires_at > ?", Time.current) }
  validates :name, :token_digest, presence: true
  validates :token_digest, uniqueness: true

  def self.issue!(organization:, name:, user: nil, scopes: ["api:read", "api:write"], expires_at: nil)
    plaintext = "sc_#{SecureRandom.hex(24)}"
    token = create!(organization:, user:, name:, scopes:, expires_at:, token_digest: digest(plaintext))
    [token, plaintext]
  end

  def self.authenticate(plaintext)
    return if plaintext.blank?
    active.find_by(token_digest: digest(plaintext))
  end

  def self.digest(plaintext)
    Digest::SHA256.hexdigest(plaintext)
  end

  def allows?(scope)
    Array(scopes).include?(scope) || Array(scopes).include?("*")
  end
end
