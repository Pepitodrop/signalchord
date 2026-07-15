#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/smoke-test-lib.sh
. "$SCRIPT_DIR/smoke-test-lib.sh"

SMOKE_ATTEMPTS=3
SMOKE_INTERVAL_SECONDS=0
callback_attempts=0

succeeds_on_second_attempt() {
  callback_attempts=$((callback_attempts + 1))
  [ "$callback_attempts" -ge 2 ]
}

always_fails() {
  return 1
}

wait_for "eventual success" succeeds_on_second_attempt
[ "$callback_attempts" -eq 2 ]

if wait_for "expected failure" always_fails 2>/dev/null; then
  echo "wait_for unexpectedly accepted a permanently failing check" >&2
  exit 1
fi

echo "smoke-test retry helper tests passed"
