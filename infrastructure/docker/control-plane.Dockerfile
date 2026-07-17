FROM ruby:3.4.10-slim-bookworm@sha256:2613ede26be10a994c32cd3356096fa34dfd5625d223df62099a4621c0a56f5f AS build
ENV BUNDLE_WITHOUT="development" BUNDLE_PATH=/usr/local/bundle BUNDLE_FROZEN=true
WORKDIR /workspace/apps/control-plane
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends build-essential libpq-dev git \
 && rm -rf /var/lib/apt/lists/*
COPY apps/control-plane/Gemfile ./Gemfile
COPY apps/control-plane/Gemfile.lock* ./
RUN bundle install --jobs=4 --retry=3
COPY apps/control-plane/ ./
COPY velato/ /workspace/velato/
RUN bundle exec bootsnap precompile --gemfile app/ config/ || true

FROM ruby:3.4.10-slim-bookworm@sha256:2613ede26be10a994c32cd3356096fa34dfd5625d223df62099a4621c0a56f5f
ENV RAILS_ENV=production RAILS_LOG_TO_STDOUT=1 RAILS_SERVE_STATIC_FILES=0 BUNDLE_WITHOUT="development" BUNDLE_PATH=/usr/local/bundle BUNDLE_FROZEN=true
WORKDIR /workspace/apps/control-plane
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends libpq5 curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 signalchord
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --from=build /workspace/apps/control-plane /workspace/apps/control-plane
COPY --from=build /workspace/velato /workspace/velato
RUN chown -R signalchord:signalchord /workspace
USER signalchord
EXPOSE 3000
CMD ["bin/rails", "server", "-b", "0.0.0.0", "-p", "3000"]
