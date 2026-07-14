require "digest"
require "securerandom"

class Invitation < ApplicationRecord
  TOKEN_PREFIX = "sc_inv_".freeze

  belongs_to :organization
  belongs_to :accepted_by, class_name: "User", optional: true

  normalizes :email, with: ->(value) { value.strip.downcase }
  validates :email, :role, :token_digest, :expires_at, presence: true
  validates :role, inclusion: { in: Membership::ROLES - ["owner"] }
  validates :token_digest, uniqueness: true
  validate :not_already_closed, on: :create

  scope :open, -> { where(accepted_at: nil, revoked_at: nil).where("expires_at > ?", Time.current) }

  def self.issue!(organization:, email:, role:, invited_by_user_id:, expires_at: 14.days.from_now)
    plaintext = "#{TOKEN_PREFIX}#{SecureRandom.urlsafe_base64(32)}"
    invitation = create!(
      organization:,
      email:,
      role:,
      invited_by_user_id:,
      expires_at:,
      token_digest: digest(plaintext)
    )
    [invitation, plaintext]
  end

  def self.authenticate(plaintext)
    return if plaintext.blank?

    open.find_by(token_digest: digest(plaintext))
  end

  def self.digest(plaintext)
    Digest::SHA256.hexdigest(plaintext)
  end

  def closed?
    accepted_at.present? || revoked_at.present? || expires_at <= Time.current
  end

  private

  def not_already_closed
    errors.add(:base, "invitation is already closed") if closed?
  end
end
