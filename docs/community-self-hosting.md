# Community self-hosting without mandatory paid services

SignalChord is a personal open-source project. The repository-owned reference flow must remain runnable without a commercial SaaS subscription, paid API key, or proprietary model service.

## Default community stack

| Component | Role | Community licence position | Mandatory payment |
| --- | --- | --- | --- |
| Apache Kafka | Event streaming | Apache License 2.0 | No |
| PostgreSQL | Control-plane database | PostgreSQL License | No |
| Neo4j Community Edition | Knowledge graph | GPLv3 | No |
| Valkey | Deduplication, cache and session-compatible storage | BSD 3-Clause | No |
| MinIO Community | S3-compatible object storage | AGPLv3 | No |
| OpenSearch | Search and projections | Apache License 2.0 | No |
| OpenTelemetry Collector | Telemetry transport | Apache License 2.0 | No |
| Prometheus | Metrics | Apache License 2.0 | No |
| Grafana OSS | Dashboards | AGPLv3 | No |

SignalChord uses each database or infrastructure component as a separate service. Its original source remains Apache-2.0; third-party components retain their own licences. Contributors modifying AGPL components must comply with those components' source-availability obligations.

## Removed from the required path

The community reference stack does not require:

- Confluent Platform container images;
- Confluent Schema Registry;
- Kafka Connect or the Neo4j Kafka Connect plugin;
- Redis 7.4+ under RSALv2/SSPLv1;
- OpenAI, Anthropic or another paid LLM API;
- a managed cloud database;
- a commercial observability backend;
- a billing provider;
- a paid email or push-notification provider.

Versioned Protobuf files and CI compatibility checks provide the repository's schema discipline. A first-party Kafka consumer projects graph mutations into Neo4j, so Kafka Connect is not required.

## Optional services that may cost money

The following are optional deployment choices, not repository requirements:

- cloud compute, managed Kubernetes or managed databases;
- a domain name and public TLS termination;
- transactional email delivery;
- Apple or Google mobile-store accounts and push credentials;
- paging/SMS services;
- paid news feeds, datasets or model weights;
- independent penetration testing.

A user may replace any of these with a self-hosted implementation, omit the related feature, or accept the external cost. Optional integrations must fail closed or remain disabled when credentials are absent.

## Local runtime

Docker Engine and Docker Compose are the verified reference runtime. Personal-use Docker Desktop may also work, but contributors who want an entirely community-hosted toolchain can use Docker Engine on Linux. Alternative container engines are welcome when they pass the same Compose and smoke tests.

## Project scope

The public repository can be released as a fun open-source alpha without implementing commercial billing, contractual support, mobile-store distribution or a paid provider stack. Those features are not prerequisites for source publication. They become relevant only when operating a public multi-user service with real customer data.
