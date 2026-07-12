# Licensing decision and publication checklist

SignalChord's original repository code is licensed under Apache License 2.0. The root `LICENSE` contains the selected license and `NOTICE` records repository-level notices.

Apache 2.0 is a suitable project license because it is permissive and includes an express patent grant. It does **not** grant rights to third-party content, services, data, model weights, trademarks or separately licensed dependencies.

Before a public release:

- retain dependency manifests and lockfiles so automated license review is reproducible;
- confirm that repository-owned fixtures contain no third-party article text or restricted assets;
- document attribution required by copied specifications, examples or assets;
- keep publisher/source terms and raw licensed content outside the code license;
- review the licenses and commercial terms of Neo4j editions, hosted services, connector plugins, model weights and datasets used in deployment;
- require contributors to certify that they have the right to submit their changes, preferably through a Developer Certificate of Origin or an explicit contributor agreement if the project later needs one.

A future dual-license or enterprise add-on decision should be recorded prospectively in an ADR. It must not retroactively change rights already granted under published Apache-2.0 releases.
