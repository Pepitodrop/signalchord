# graph-analytics

Tenant-bounded Neo4j analytics for explainable signals. The service uses an ephemeral Neo4j Graph Data Science projection for degree centrality when GDS is available, then drops the projection. Community/local environments may use the explicitly labeled Cypher fallback. Source diversity, recent relationship changes, method and evidence path identifiers are returned with every result.
