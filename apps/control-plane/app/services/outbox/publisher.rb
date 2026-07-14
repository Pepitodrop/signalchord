module Outbox
  class Publisher
    BATCH_SIZE = 100

    def initialize(kafka: nil)
      @kafka = kafka || Kafka.new(**ProductionConfig.kafka_options)
    end

    def publish_batch
      producer = @kafka.producer(required_acks: :all, max_retries: 5, retry_backoff: 1)
      events = claim_pending_events
      events.each do |event|
        producer.produce(JSON.generate(envelope(event)), topic: event.topic, key: event.partition_key)
      end
      producer.deliver_messages unless events.empty?
      OutboxEvent.where(id: events.map(&:id)).update_all(published_at: Time.current, updated_at: Time.current, last_error: nil)
      events.length
    rescue StandardError => error
      OutboxEvent.where(id: events.to_a.map(&:id)).update_all(
        publish_attempts: Arel.sql("publish_attempts + 1"),
        last_error: error.message.truncate(2_000),
        updated_at: Time.current
      ) if defined?(events)
      Rails.logger.error(message: "outbox publish failed", error: error.class.name)
      raise
    ensure
      producer&.shutdown
    end

    private

    def claim_pending_events
      OutboxEvent.transaction do
        events = OutboxEvent.pending.lock("FOR UPDATE SKIP LOCKED").limit(BATCH_SIZE).to_a
        OutboxEvent.where(id: events.map(&:id)).update_all(
          publish_attempts: Arel.sql("publish_attempts + 1"),
          updated_at: Time.current
        ) unless events.empty?
        events
      end
    end

    def envelope(event)
      {
        event_id: event.id,
        event_type: event.event_type,
        schema_version: event.schema_version,
        tenant_id: event.tenant_id,
        occurred_at: event.occurred_at.iso8601(6),
        ingested_at: Time.current.iso8601(6),
        correlation_id: event.correlation_id,
        causation_id: event.causation_id,
        origin: "control-plane",
        processing_stage: "transactional-outbox",
        idempotency_key: "outbox:#{event.id}",
        payload: event.payload
      }
    end
  end
end
