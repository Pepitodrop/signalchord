class User < ApplicationRecord
  has_secure_password
  has_many :memberships, dependent: :destroy
  has_many :organizations, through: :memberships
  has_many :notification_endpoints, dependent: :destroy

  normalizes :email, with: ->(value) { value.strip.downcase }
  validates :email, presence: true, uniqueness: true

  # Verification tokens are Rails' built-in signed/expiring tokens (Rails 8
  # ActiveRecord::TokenFor), not a hand-rolled digest table. Scoping on
  # [email_verified_at, verification_email_sent_at] gives single-use for free:
  # once email_verified_at changes, every previously issued token's embedded
  # digest stops matching, so it can never be replayed. Bumping
  # verification_email_sent_at on resend invalidates any still-outstanding
  # older link the same way.
  generates_token_for :email_verification, expires_in: ENV.fetch("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24).to_i.hours do
    [email_verified_at, verification_email_sent_at]
  end

  def disabled?
    disabled_at.present?
  end

  def email_verified?
    email_verified_at.present?
  end

  # Shared by SignupsController#create and EmailVerificationsController#resend
  # so the "bump timestamp, generate token, send mail, swallow+log delivery
  # failures" sequence lives in exactly one place.
  def send_verification_email!
    update!(verification_email_sent_at: Time.current)
    token = generate_token_for(:email_verification)
    OnboardingMailer.verification_email(self, token).deliver_now
  rescue StandardError => error
    # Deliberate: the account/state change already happened even if delivery
    # fails (SMTP outage, timeout, misconfigured provider). "Resend" is the
    # recovery path — failing the caller here would be a worse UX than one
    # resend click.
    Rails.logger.error(
      "[verification_email] failed to send to user #{id}: #{error.class}: #{error.message}"
    )
  end
end
