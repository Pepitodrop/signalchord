# Shared cookie handling for the web session (an httpOnly, Secure, encrypted
# cookie carrying the same opaque ApiToken plaintext the Authorization: Bearer
# header carries for mobile/scripted clients). Included by ApplicationController
# (to read it), and by any controller that issues or clears it
# (WebSessionsController, OrganizationsController).
module CookieSession
  extend ActiveSupport::Concern

  # ActionController::API (used by ApplicationController and the standalone
  # pre-auth controllers) does not include cookie support by default — this
  # wires it into whichever controller includes this concern.
  included do
    include ActionController::Cookies
  end

  SESSION_COOKIE_NAME = ENV.fetch("SESSION_COOKIE_NAME", "sc_session").freeze

  private

  def write_session_cookie(plaintext)
    cookies.encrypted[SESSION_COOKIE_NAME] = {
      value: plaintext,
      httponly: true,
      secure: Rails.env.production?,
      same_site: :lax,
      expires: 30.days
    }
  end

  def clear_session_cookie
    cookies.delete(SESSION_COOKIE_NAME)
  end

  def bearer_token_from_cookie
    cookies.encrypted[SESSION_COOKIE_NAME]
  end
end
