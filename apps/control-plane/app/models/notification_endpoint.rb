require "digest"

class NotificationEndpoint < ApplicationRecord
  PLATFORMS = %w[expo ios android webhook].freeze

  belongs_to :organization
  belongs_to :user
  has_many :notification_deliveries, dependent: :destroy

  validates :platform, inclusion: { in: PLATFORMS }
  validates :token_digest, :token_ciphertext, presence: true
  validates :token_digest, uniqueness: { scope: :organization_id }

  scope :enabled, -> { where(enabled: true) }

  def self.register!(organization:, user:, platform:, token:)
    digest = Digest::SHA256.hexdigest(token)
    endpoint = find_or_initialize_by(organization:, token_digest: digest)
    endpoint.assign_attributes(
      user:,
      platform:,
      token_ciphertext: TokenCipher.encrypt(token),
      enabled: true,
      last_seen_at: Time.current
    )
    endpoint.save!
    endpoint
  end

  def delivery_token
    TokenCipher.decrypt(token_ciphertext)
  end
end
