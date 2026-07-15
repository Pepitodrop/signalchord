#!/usr/bin/env sh
# Shared bounded-retry helpers for integration smoke tests.

wait_for() {
  description=$1
  shift
  attempts=${SMOKE_ATTEMPTS:-60}
  interval=${SMOKE_INTERVAL_SECONDS:-2}
  current=1

  while [ "$current" -le "$attempts" ]; do
    if "$@"; then
      return 0
    fi
    if [ "$current" -lt "$attempts" ]; then
      sleep "$interval"
    fi
    current=$((current + 1))
  done

  echo "Timed out waiting for ${description} after ${attempts} attempts" >&2
  return 1
}
