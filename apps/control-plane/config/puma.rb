max_threads = ENV.fetch("RAILS_MAX_THREADS", 5)
threads max_threads, max_threads
port ENV.fetch("PORT", 3000)
environment ENV.fetch("RAILS_ENV", "development")
pidfile ENV["PIDFILE"] if ENV["PIDFILE"]
plugin :tmp_restart
