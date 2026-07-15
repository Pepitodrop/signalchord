# Licensing decision and publication checklist

SignalChord's original repository code is licensed under Apache License 2.0. The root `LICENSE` contains the selected license and `NOTICE` records repository-level notices.

Apache 2.0 is a suitable project license because it is permissive and includes an express patent grant. It does **not** grant rights to third-party content, services, data, model weights, trademarks or separately licensed dependencies.

The verified community runtime deliberately avoids mandatory paid APIs and source-available infrastructure where a mature open-source replacement is available. It uses the official Apache Kafka image and Valkey instead of Confluent Platform and Redis 7.4+. Confluent Schema Registry and Kafka Connect are not required by the repository-owned vertical slice.

Before a public release:

- retain dependency manifests and lockfiles so automated license review is reproducible;
- confirm that repository-owned fixtures contain no third-party article text or restricted assets;
- document attribution required by copied specifications, examples or assets;
- keep publisher/source terms and raw licensed content outside the code license;
- preserve the separate licence notices for Neo4j Community, MinIO, Grafana OSS and other runtime components;
- review any optional hosted service, connector plugin, model weight or dataset before adding it to the verified path;
- run `python3 scripts/validate_community_stack.py` and its regression tests;
- require contributors to certify that they have the right to submit their changes, preferably through a Developer Certificate of Origin or an explicit contributor agreement if the project later needs one.

A future dual-license or enterprise add-on decision should be recorded prospectively in an ADR. It must not retroactively change rights already granted under published Apache-2.0 releases.
