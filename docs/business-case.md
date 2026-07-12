# SignalChord small business case

## Executive summary

SignalChord is a real-time news intelligence platform that transforms fragmented articles and public reports into an explainable, continuously updated knowledge graph.

It helps research, risk, strategy, journalism and competitive-intelligence teams understand not only what was published, but also which people, companies, claims, events and sources are connected.

## Problem

Professional users face too many disconnected sources, repeated syndicated content, weak claim provenance, difficult cross-article relationship tracing, slow manual monitoring, alert fatigue, opaque automation and poor reconstruction of story evolution.

## Target customers

Primary customers are corporate intelligence teams, strategy departments, risk and compliance teams, investigative journalists, financial research teams, public-affairs teams and cyber-threat-intelligence teams. Secondary customers include universities, NGOs, government analysts and specialist research firms.

## Value proposition

SignalChord provides real-time monitoring, relationship-based discovery, explainable alerts, claim corroboration, contradiction detection, temporal story reconstruction, source provenance, custom intelligence policies and coordinated web/mobile workflows.

## Differentiation

1. Kafka-native real-time and replayable processing.
2. Neo4j-native relationship analysis.
3. Evidence-first intelligence.
4. Temporal claim and entity modeling.
5. User-configurable alert policies.
6. Velato MIDI policies as a programmable and audible policy format.
7. Full replay and auditability.
8. Web and mobile analyst workflows.

## Initial commercial model

Illustrative assumptions—not verified market prices:

| Plan | Assumed monthly price | Intended scope |
|---|---:|---|
| Developer | €0 | local/self-hosted evaluation and limited sources |
| Professional | €99–€249 | individual analyst, limited retention and alerts |
| Team | €1,000–€4,000 | 5–20 analysts, shared investigations and governance |
| Enterprise | €25,000–€150,000 annually | SSO, private sources, extended retention and support |
| Private cloud/on-premises | custom | isolated deployment and integration services |
| API usage | metered | event, search, graph and alert API consumption |

## MVP commercial hypothesis

A small intelligence team will pay when SignalChord reliably monitors a watchlist, reduces duplicate news, exposes meaningful relationships, explains every alert, shows supporting and contradicting evidence, and delivers relevant alerts quickly.

## Initial success metrics

Weekly active analysts, watchlists per workspace, alert open rate, relevance feedback, publication-to-graph latency, duplicate reduction, entity-resolution precision, claim-extraction precision, investigations created, estimated analyst hours saved, trial-to-paid conversion and team-plan net revenue retention.

## Risks, mitigation and owner

| Risk | Mitigation | Accountable owner |
|---|---|---|
| Source licensing | rights registry, policy enforcement, deletion workflow, legal review | Product + Legal |
| Copyright | raw-object access controls, snippet limits, link-first UI | Legal + Data Governance |
| Extraction errors | confidence thresholds, evidence display, evaluation fixtures | ML Engineering |
| Entity-resolution mistakes | candidate preservation, merge/unmerge and review queue | ML + Product |
| Defamation/sensitive claims | source-vs-inference labels, review gates, takedown process | Legal + Trust & Safety |
| Model bias | segmented evaluation and human escalation | ML + Governance |
| Infrastructure cost | per-tenant metering, retention tiers, batching and budgets | Platform Engineering |
| Low alert precision | feedback loop, policy simulation, threshold calibration | Product + ML |
| Product complexity | narrow initial segment and guided investigations | Product Design |
| Velato maintainability | constrained IR, versioned spec, fallback engine | Policy Engine Owner |
| Customer trust | audit trails, provenance, published quality metrics | Product + Security |

## Go-to-market

Start with competitive intelligence for technology companies. Recruit five to ten design-partner teams, provide a defined source/watchlist onboarding workflow, run weekly relevance reviews, publish quantified case studies of analyst time saved, use a limited source set with clear rights and offer a paid pilot with explicit success criteria.

## Funding and cost assumptions

Illustrative monthly operating scenarios, excluding founder compensation and taxes:

| Cost category | Low | Base | High | Notes |
|---|---:|---:|---:|---|
| Cloud infrastructure | €800 | €4,000 | €15,000 | Kafka/Neo4j/search volume dominates |
| Data licensing | €0 | €5,000 | €40,000 | depends entirely on source agreements |
| Engineering | €15,000 | €50,000 | €120,000 | contractor/salary blend assumption |
| Model inference | €300 | €3,000 | €20,000 | model and throughput dependent |
| Observability | €150 | €1,000 | €6,000 | managed vs self-hosted |
| Security | €250 | €2,000 | €15,000 | tooling, reviews and testing |
| Legal/compliance | €1,000 | €5,000 | €20,000 | source contracts and sensitive claims |
| Customer support | €500 | €4,000 | €15,000 | pilot vs enterprise support |

These values are planning assumptions, not verified market data. The first commercial validation should test willingness to pay before scaling licensed data or 24/7 infrastructure.
