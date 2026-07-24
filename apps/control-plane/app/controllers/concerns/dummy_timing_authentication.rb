# Shared by the 3 login controllers (WebSessionsController, AuthController,
# OrganizationsController#create) so the timing fix lives in one place. Not a
# private ApplicationController method: WebSessionsController and
# AuthController both inherit ActionController::API directly, not
# ApplicationController, so a shared concern (mirroring CookieSession's
# pattern) is the only way to reuse this across all 3.
module DummyTimingAuthentication
  extend ActiveSupport::Concern

  private

  # `user&.authenticate(password)` short-circuits via &. when the email
  # doesn't exist, so bcrypt (deliberately slow) only ever runs for real
  # accounts — a measurable, code-confirmed enumeration oracle (Blocker #8).
  # When there's no user to check, still run a real bcrypt hash of the
  # submitted password so response timing doesn't correlate with whether the
  # account exists.
  def authenticate_with_dummy_timing(user, password)
    return user.authenticate(password) if user

    BCrypt::Password.create(password)
    false
  end
end
