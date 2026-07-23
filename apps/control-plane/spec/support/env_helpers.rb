# Temporarily overrides ENV vars for the duration of a block, restoring the
# original values (or absence) afterward — used by specs that need to prove
# behavior differs by SIGNALCHORD_ENV/RAILS_ALLOWED_HOSTS without permanently
# mutating the test process's environment.
module EnvHelpers
  def with_env(overrides)
    originals = overrides.keys.to_h { |key| [key, ENV[key]] }
    overrides.each { |key, value| ENV[key] = value }
    yield
  ensure
    originals.each { |key, value| value.nil? ? ENV.delete(key) : ENV[key] = value }
  end
end

RSpec.configure { |config| config.include EnvHelpers }
