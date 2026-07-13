MERGE (s:Source {stable_id:'source:example-tech'}) SET s.name='Example Technology Wire',s.status='active';
MERGE (d:Document {stable_id:'doc:sample-1'}) SET d.content_hash='fixture',d.observed_at=datetime();
MERGE (a:Article {stable_id:'article:sample-1'}) SET a.title='Acme announces Northstar partnership',a.observed_at=datetime();
MERGE (c:Company {stable_id:'company:acme'}) SET c.name='Acme Corporation',c.status='model_verified',c.confidence=.98;
MERGE (n:Organization {stable_id:'org:northstar'}) SET n.name='Northstar Labs',n.status='candidate',n.confidence=.91;
MERGE (e:Evidence {stable_id:'evidence:sample-1'}) SET e.document_id=d.stable_id,e.kind='model_extraction',e.confidence=.91;
MERGE (a)-[:PUBLISHED]->(s)
MERGE (a)-[:DERIVED_FROM]->(d)
MERGE (a)-[:MENTIONS {confidence:.98,observed_at:datetime()}]->(c)
MERGE (a)-[:MENTIONS {confidence:.91,observed_at:datetime()}]->(n)
MERGE (c)-[:PARTNERED_WITH {stable_id:'rel:sample-1',status:'candidate',confidence:.91,observed_at:datetime(),valid_from:datetime()}]->(n)
MERGE (e)-[:EVIDENCE_FOR]->(c);
