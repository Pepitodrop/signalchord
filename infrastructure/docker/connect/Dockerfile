FROM confluentinc/cp-kafka-connect:7.7.1@sha256:c5872175ca3a6d15456adfb644c68a77050c106ea1e11a4cd7f2417a16e00037
USER root
RUN mkdir -p /usr/share/java/neo4j \
 && curl --fail --location --retry 3 \
    https://github.com/neo4j/neo4j-kafka-connector/releases/download/5.5.0/neo4j-kafka-connect-5.5.0.jar \
    --output /usr/share/java/neo4j/neo4j-kafka-connect-5.5.0.jar \
 && chown -R appuser:appuser /usr/share/java/neo4j
USER appuser
