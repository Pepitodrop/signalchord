#!/usr/bin/env sh
set -eu
docker compose --profile slice down --volumes --remove-orphans
printf '%s\n' "SignalChord local state removed."
