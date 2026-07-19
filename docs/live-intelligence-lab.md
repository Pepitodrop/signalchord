# Live Intelligence Lab

SignalChord exposes an optional authenticated visualization at `/lab.html`.

## What it shows

- a tenant-scoped knowledge-graph projection for a selected stable entity ID;
- node, relationship, alert and realtime-event counts;
- graph-growth history sampled by the browser;
- an API-observed article-to-alert pipeline pulse;
- the checked-in Merzato speech programs;
- readable German speech translations generated from the executable `.merz` source;
- browser text-to-speech playback using a German system voice when available;
- a playable one-minute Velato policy score.

## Audio behavior

The web player explicitly unlocks the Web Audio context from the user's click, supports the prefixed mobile Web Audio constructor, raises low executable notes by one octave for phone speakers, adds a quiet octave layer, and uses a dynamics compressor plus adjustable output gain. These changes affect only audible rendering; the executable MIDI and policy semantics remain unchanged.

Long Merzato speeches are split into short sentence chunks before being queued through the browser Speech Synthesis API. This avoids the common mobile-browser failure mode where a single long utterance stops silently. The generated transcript remains readable when the browser or operating system has no German text-to-speech voice.

## Content Security Policy

The production web image keeps `script-src 'self'` and does not enable inline JavaScript. Nginx injects the audited, self-hosted `/lab.js` file into `/lab.html`; the old inline bootstrap remains blocked by policy. This fixes the previous production failure where the lab's controls appeared but its inline JavaScript, including audio playback, could not execute.

## Privacy and security boundary

The lab does **not** connect directly to Neo4j or Kafka. It does not receive database credentials, Kafka administration credentials, consumer-group details, raw Kafka payloads, full graph properties or cross-tenant data.

It reuses the authenticated browser session and calls the same tenant-scoped SignalChord APIs as the analyst application. The graph view intentionally renders only stable IDs, display labels and relationship types returned by the graph-query API. The pipeline view is an observed workflow visualization based on safe API counts and authenticated realtime events; it is not a Kafka administration console and does not claim to expose exact broker lag.

Operators should keep Neo4j, Kafka, PostgreSQL, MinIO, Valkey and OpenSearch bound to private interfaces or cluster-internal services. Only the authenticated web/API/realtime surface should be internet-accessible.

## Creative programs

- `apps/web/public/programs/merz/meme-cabinet.merz` is a long executable Merzato speech program. It uses every documented meme alias or marker, calls the `helfer` agenda-point function and performs real VM arithmetic and control flow.
- `apps/web/public/programs/merz/graph-growth-briefing.merz` calculates a bounded graph-momentum score through the callable `graph_score` function.
- `velato/programs/live-graph-minute.vasm` is a 100-instruction functional policy. At 100 BPM and one beat per instruction, the browser performance lasts approximately one minute. It writes all four policy outputs and is round-trip tested through the Velato MIDI engine.

The satire files are fictional programming-language examples, not quotation or impersonation claims.
