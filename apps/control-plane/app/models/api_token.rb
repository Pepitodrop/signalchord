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

  # Shared by ApplicationController (web/mobile requests) and
  # Internal::V1::TokensController (service-to-service SSE auth) so "what
  # counts as disabled" is defined in exactly one place. Tokens with no
  # bound user (user_id nil) have no membership to check, so they're never
  # considered disabled here.
  #
  # membership: pass an already-resolved Membership to reuse a caller's own
  # memoized lookup (ApplicationController#current_membership already
  # queries this once per request) instead of a second query for the same row.
  def user_or_membership_disabled?(membership: nil)
    return false unless user_id

    membership ||= Membership.find_by(organization_id:, user_id:)
    user.nil? || user.disabled? || membership.nil? || membership.disabled?
  end
end
