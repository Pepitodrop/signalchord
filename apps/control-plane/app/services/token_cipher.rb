require "base64"
require "digest"
require "openssl"

class TokenCipher
  class << self
    def encrypt(plaintext)
      cipher = OpenSSL::Cipher.new("aes-256-gcm").encrypt
      cipher.key = key
      iv = OpenSSL::Random.random_bytes(12)
      cipher.iv = iv
      cipher.auth_data = "signalchord-notification-token-v1"
      encrypted = cipher.update(plaintext) + cipher.final
      Base64.strict_encode64(iv + cipher.auth_tag + encrypted)
    end

    def decrypt(encoded)
      data = Base64.strict_decode64(encoded)
      cipher = OpenSSL::Cipher.new("aes-256-gcm").decrypt
      cipher.key = key
      cipher.iv = data.byteslice(0, 12)
      cipher.auth_tag = data.byteslice(12, 16)
      cipher.auth_data = "signalchord-notification-token-v1"
      cipher.update(data.byteslice(28..)) + cipher.final
    end

    private

    def key
      Digest::SHA256.digest(ENV.fetch("NOTIFICATION_TOKEN_ENCRYPTION_KEY", "signalchord-local-notification-key"))
    end
  end
end
