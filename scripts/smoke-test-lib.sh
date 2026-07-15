#!/usr/bin/env sh
# Shared bounded-retry helpers for integration smoke tests.

wait_for() {
  _wait_for_description=$1
  shift
  _wait_for_limit=${SMOKE_ATTEMPTS:-60}
  _wait_for_interval=${SMOKE_INTERVAL_SECONDS:-2}
  _wait_for_current=1

  while [ "$_wait_for_current" -le "$_wait_for_limit" ]; do
    if "$@"; then
      return 0
    fi
    if [ "$_wait_for_current" -lt "$_wait_for_limit" ]; then
      sleep "$_wait_for_interval"
    fi
    _wait_for_current=$((_wait_for_current + 1))
  done

  echo "Timed out waiting for ${_wait_for_description} after ${_wait_for_limit} attempts" >&2
  return 1
}
