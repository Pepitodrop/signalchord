#!/usr/bin/env sh
set -eu

curl --fail --silent --show-error \
  --request PUT \
  --header 'Content-Type: application/json' \
  --data-binary '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false,"cluster.blocks.create_index":false}}' \
  http://localhost:9200/_cluster/settings >/dev/null
