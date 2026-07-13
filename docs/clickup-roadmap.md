# ClickUp roadmap

This file is the reviewable source before any ClickUp API mutation. Task dependencies should be created in ClickUp where the API/workspace supports them; the CSV/JSON preserve dependency text for manual import.

## Lists

- Product and Architecture
- Platform and Infrastructure
- Kafka Streaming
- Neo4j Knowledge Graph
- Ingestion
- NLP and Machine Intelligence
- Rails Control Plane
- Web Application
- Mobile Application
- Velato Policy Engine
- Security and Governance
- Testing and Release

## Statuses

`Backlog` → `Ready` → `In Progress` → `In Review` → `Blocked` / `Done`

## Milestone 0 — Foundation

Primary list: **Product and Architecture**

- Confirm product scope
- Create architecture decision records
- Initialize monorepo
- Set up CI
- Create Docker development environment
- Define event standards
- Define graph model
- Create security baseline

## Milestone 1 — Streaming ingestion

Primary list: **Kafka Streaming**

- Implement source registry
- Implement RSS collector
- Implement document fetcher
- Define Kafka schemas
- Add normalization
- Add deduplication
- Add object storage
- Add dead-letter handling

## Milestone 2 — Knowledge extraction

Primary list: **NLP and Machine Intelligence**

- Implement NLP pipeline
- Add named-entity extraction
- Add claim extraction
- Add relation extraction
- Add embeddings
- Add evaluation fixtures

## Milestone 3 — Knowledge graph

Primary list: **Neo4j Knowledge Graph**

- Create Neo4j constraints and indexes
- Create Kafka sink configuration
- Implement idempotent mutations
- Add provenance
- Add temporal relationships
- Add CDC source connector
- Add graph-query service

## Milestone 4 — Product control plane

Primary list: **Rails Control Plane**

- Add users and organizations
- Add source management
- Add watchlists
- Add saved investigations
- Add audit logs
- Add API authorization
- Add notification preferences

## Milestone 5 — Analyst web application

Primary list: **Web Application**

- Add dashboard
- Add search
- Add entity pages
- Add article comparison
- Add graph explorer
- Add timeline
- Add alert inbox
- Add investigation workspace

## Milestone 6 — Velato intelligence policies

Primary list: **Velato Policy Engine**

- Define policy register contract
- Implement MIDI upload
- Implement Velato parsing
- Implement safe intermediate representation
- Implement sandbox
- Ship default MIDI policies
- Add visual composer
- Add simulation view
- Add policy audit trail

## Milestone 7 — Mobile application

Primary list: **Mobile Application**

- Add Expo project
- Add authentication
- Add watchlists
- Add alerts
- Add push notifications
- Add entity views
- Add story timelines
- Add simplified graph
- Add offline cache

## Milestone 8 — Hardening and beta

Primary list: **Testing and Release**

- Add load tests
- Add replay tests
- Add security testing
- Add observability dashboards
- Add backup and restore
- Add source-governance workflows
- Conduct closed beta
- Resolve launch blockers
