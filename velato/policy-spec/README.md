# SignalChord Velato policy contract

Inputs are normalized scalar registers named `source_trust`, `corroboration_count`, `contradiction_count`, `novelty`, `entity_relevance`, `graph_centrality`, `geographic_relevance`, `watchlist_match`, `recency` and `source_diversity`.

Outputs are `alert_score` 0–100, `severity_code` 0–9, `routing_code` 0–255 and optional suppression.

MIDI source, compiler version, normalized IR, input vector, output, instruction count, execution duration, rejection reason and trace hash are retained for every simulation and activation. The conventional fallback rules engine is authoritative when the Velato worker is unavailable or rejects a program.
