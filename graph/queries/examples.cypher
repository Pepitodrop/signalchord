// Entity timeline
MATCH (e {stable_id: $entity_id})<-[r:ABOUT|AFFECTS|MENTIONS]-(x)
WHERE ($tenant_id IS NULL OR x.tenant_id IS NULL OR x.tenant_id = $tenant_id)
RETURN x, r ORDER BY coalesce(r.observed_at, x.observed_at) DESC LIMIT $limit;

// Shortest approved path
MATCH (a {stable_id:$from_id}), (b {stable_id:$to_id})
MATCH p=shortestPath((a)-[*..6]-(b))
WHERE all(n IN nodes(p) WHERE n.tenant_id IS NULL OR n.tenant_id=$tenant_id)
RETURN p;

// Contradictory claims
MATCH (c1:Claim)-[r:CONTRADICTS]->(c2:Claim)
WHERE c1.status <> 'retracted' AND c2.status <> 'retracted'
RETURN c1,c2,r ORDER BY r.confidence DESC LIMIT $limit;

// Corroborated claims and source diversity
MATCH (cluster:Claim)<-[:CORROBORATES]-(claim:Claim)<-[:MAKES_CLAIM]-(article:Article)-[:PUBLISHED]->(source:Source)
WITH cluster, count(DISTINCT claim) AS corroboration_count, count(DISTINCT source) AS source_diversity
RETURN cluster, corroboration_count, source_diversity ORDER BY source_diversity DESC LIMIT $limit;

// Articles affecting a watched entity
MATCH (w:Watchlist {tenant_id:$tenant_id})-[:WATCHES]->(e)<-[:AFFECTS|ABOUT|MENTIONS]-(a:Article)
WHERE w.stable_id=$watchlist_id AND a.observed_at >= datetime($from)
RETURN a,e ORDER BY a.observed_at DESC LIMIT $limit;

// Organization relationship changes
MATCH (o:Organization {stable_id:$entity_id})-[r]-(other)
WHERE r.observed_at >= datetime($from) AND type(r) IN $relationship_types
RETURN type(r),other,r ORDER BY r.observed_at DESC LIMIT $limit;

// Claims propagated across publishers
MATCH (cluster:Claim)<-[:CORROBORATES]-(claim:Claim)<-[:MAKES_CLAIM]-(article:Article)-[:PUBLISHED]->(source:Source)-[:MEMBER_OF]->(publisher:Publisher)
WITH cluster, collect(DISTINCT publisher) AS publishers
WHERE size(publishers) >= $minimum_publishers
RETURN cluster,publishers LIMIT $limit;

// Event to affected companies
MATCH p=(event:Event {stable_id:$event_id})-[:AFFECTS|RELATED_TO*1..4]->(company:Company)
RETURN p LIMIT $limit;
