package kafkautil

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"testing"
	"time"

	"github.com/IBM/sarama"
)

// --- fakes ---------------------------------------------------------------

type fakeSession struct {
	ctx    context.Context
	marked []*sarama.ConsumerMessage
	events *[]string
}

func (s *fakeSession) Claims() map[string][]int32               { return nil }
func (s *fakeSession) MemberID() string                         { return "test-member" }
func (s *fakeSession) GenerationID() int32                      { return 1 }
func (s *fakeSession) MarkOffset(string, int32, int64, string)  {}
func (s *fakeSession) Commit()                                  {}
func (s *fakeSession) ResetOffset(string, int32, int64, string) {}
func (s *fakeSession) Context() context.Context                 { return s.ctx }
func (s *fakeSession) MarkMessage(msg *sarama.ConsumerMessage, _ string) {
	s.marked = append(s.marked, msg)
	if s.events != nil {
		*s.events = append(*s.events, "mark")
	}
}

type fakeClaim struct {
	topic     string
	partition int32
	messages  chan *sarama.ConsumerMessage
}

func (c *fakeClaim) Topic() string                            { return c.topic }
func (c *fakeClaim) Partition() int32                         { return c.partition }
func (c *fakeClaim) InitialOffset() int64                     { return 0 }
func (c *fakeClaim) HighWaterMarkOffset() int64               { return 0 }
func (c *fakeClaim) Messages() <-chan *sarama.ConsumerMessage { return c.messages }

// fakeSyncProducer implements sarama.SyncProducer without a real broker.
type fakeSyncProducer struct {
	sendErr error
	sent    []*sarama.ProducerMessage
	events  *[]string
}

func (p *fakeSyncProducer) SendMessage(msg *sarama.ProducerMessage) (int32, int64, error) {
	if p.events != nil {
		*p.events = append(*p.events, "publish")
	}
	if p.sendErr != nil {
		return 0, 0, p.sendErr
	}
	p.sent = append(p.sent, msg)
	return 0, int64(len(p.sent) - 1), nil
}
func (p *fakeSyncProducer) SendMessages(msgs []*sarama.ProducerMessage) error {
	for _, msg := range msgs {
		if _, _, err := p.SendMessage(msg); err != nil {
			return err
		}
	}
	return nil
}
func (p *fakeSyncProducer) Close() error                            { return nil }
func (p *fakeSyncProducer) TxnStatus() sarama.ProducerTxnStatusFlag { return 0 }
func (p *fakeSyncProducer) IsTransactional() bool                   { return false }
func (p *fakeSyncProducer) BeginTxn() error                         { return nil }
func (p *fakeSyncProducer) CommitTxn() error                        { return nil }
func (p *fakeSyncProducer) AbortTxn() error                         { return nil }
func (p *fakeSyncProducer) AddOffsetsToTxn(map[string][]*sarama.PartitionOffsetMetadata, string) error {
	return nil
}
func (p *fakeSyncProducer) AddMessageToTxn(*sarama.ConsumerMessage, string, *string) error {
	return nil
}

func testMessage() *sarama.ConsumerMessage {
	return &sarama.ConsumerMessage{
		Topic:     "alert.created.v1",
		Partition: 3,
		Offset:    42,
		Key:       []byte("alert-1"),
		Value:     []byte(`{"tenant_id":"tenant-1"}`),
		Timestamp: time.Unix(1_700_000_000, 0),
		Headers: []*sarama.RecordHeader{
			{Key: []byte("trace-id"), Value: []byte("abc-123")},
		},
	}
}

// --- PermanentError / IsPermanent ----------------------------------------

func TestIsPermanent_DirectWrapIsPermanent(t *testing.T) {
	err := NewPermanentError(errors.New("bad payload"))
	if !IsPermanent(err) {
		t.Fatal("expected a direct PermanentError to be permanent")
	}
}

func TestIsPermanent_WrappedFurtherIsStillPermanent(t *testing.T) {
	inner := NewPermanentError(errors.New("bad payload"))
	wrapped := fmt.Errorf("decode failed: %w", inner)
	if !IsPermanent(wrapped) {
		t.Fatal("expected errors.As to see through fmt.Errorf %w wrapping to the PermanentError")
	}
}

func TestIsPermanent_OrdinaryErrorIsNotPermanent(t *testing.T) {
	if IsPermanent(errors.New("connection reset")) {
		t.Fatal("expected an ordinary error to remain transient")
	}
	if IsPermanent(fmt.Errorf("wrapped: %w", errors.New("connection reset"))) {
		t.Fatal("expected a wrapped ordinary error to remain transient")
	}
}

func TestIsPermanent_NilErrorIsNotPermanent(t *testing.T) {
	if IsPermanent(nil) {
		t.Fatal("expected nil to never be permanent")
	}
}

var errSentinelCause = errors.New("sentinel cause")

func TestErrorsIsSeesThroughPermanentErrorToWrappedCause(t *testing.T) {
	wrapped := NewPermanentError(fmt.Errorf("context: %w", errSentinelCause))
	if !errors.Is(wrapped, errSentinelCause) {
		t.Fatal("expected errors.Is to see through PermanentError's Unwrap to the sentinel cause")
	}
	var permanent *PermanentError
	if !errors.As(wrapped, &permanent) {
		t.Fatal("expected errors.As to recognize the PermanentError itself")
	}
}

// --- buildDLQEnvelope ------------------------------------------------------

func TestBuildDLQEnvelope_PreservesRequiredMetadata(t *testing.T) {
	message := testMessage()
	handlerErr := NewPermanentError(errors.New("missing tenant_id"))

	envelope := buildDLQEnvelope(message, handlerErr, "realtime-gateway")

	if envelope.Origin != "realtime-gateway" {
		t.Errorf("origin = %q", envelope.Origin)
	}
	if envelope.ErrorType != "*errors.errorString" {
		t.Errorf("error_type = %q", envelope.ErrorType)
	}
	if envelope.Error != "missing tenant_id" {
		t.Errorf("error = %q", envelope.Error)
	}
	if _, err := time.Parse(time.RFC3339Nano, envelope.FailedAt); err != nil {
		t.Errorf("failed_at not RFC3339: %v", err)
	}
	if envelope.SourceTopic != "alert.created.v1" {
		t.Errorf("source_topic = %q", envelope.SourceTopic)
	}
	if envelope.SourcePartition != 3 {
		t.Errorf("source_partition = %d", envelope.SourcePartition)
	}
	if envelope.SourceOffset != 42 {
		t.Errorf("source_offset = %d", envelope.SourceOffset)
	}
	if envelope.SourceTimestamp == "" {
		t.Error("source_timestamp is empty")
	}
	if envelope.Key != "alert-1" || envelope.KeyEncoding != "utf-8" {
		t.Errorf("key = %q encoding = %q", envelope.Key, envelope.KeyEncoding)
	}
	if envelope.Value != `{"tenant_id":"tenant-1"}` || envelope.ValueEncoding != "utf-8" {
		t.Errorf("value = %q encoding = %q", envelope.Value, envelope.ValueEncoding)
	}
	if len(envelope.Headers) != 1 || envelope.Headers[0].Key != "trace-id" || envelope.Headers[0].Value != "abc-123" {
		t.Errorf("headers = %+v", envelope.Headers)
	}

	// Round-trips through JSON cleanly (this is what actually gets published).
	if _, err := json.Marshal(envelope); err != nil {
		t.Fatalf("marshal envelope: %v", err)
	}
}

func TestBuildDLQEnvelope_Base64EncodesNonUTF8Values(t *testing.T) {
	message := testMessage()
	message.Key = []byte{0xff, 0xfe}
	message.Value = []byte{0xff, 0xfe, 0xfd}

	envelope := buildDLQEnvelope(message, errors.New("bad"), "test")

	if envelope.KeyEncoding != "base64" {
		t.Errorf("key_encoding = %q, want base64", envelope.KeyEncoding)
	}
	if envelope.ValueEncoding != "base64" {
		t.Errorf("value_encoding = %q, want base64", envelope.ValueEncoding)
	}
}

// --- ConsumeClaim / DLQ integration ---------------------------------------

func TestConsumeClaim_SuccessfulProcessingMarksOnceAndSkipsDLQ(t *testing.T) {
	messages := make(chan *sarama.ConsumerMessage, 1)
	message := testMessage()
	messages <- message
	close(messages)

	producer := &fakeSyncProducer{}
	session := &fakeSession{ctx: context.Background()}
	handler := groupHandler{
		handle: func(context.Context, *sarama.ConsumerMessage) error { return nil },
		dlq:    &DLQConfig{Producer: &Producer{p: producer}, Origin: "test"},
	}

	if err := handler.ConsumeClaim(session, &fakeClaim{messages: messages}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(session.marked) != 1 || session.marked[0] != message {
		t.Fatalf("marked = %v, want exactly the one message", session.marked)
	}
	if len(producer.sent) != 0 {
		t.Fatalf("expected no DLQ publish on success, got %d", len(producer.sent))
	}
}

func TestConsumeClaim_PermanentErrorPublishesToDLQThenMarksInOrder(t *testing.T) {
	messages := make(chan *sarama.ConsumerMessage, 1)
	message := testMessage()
	messages <- message
	close(messages)

	var events []string
	producer := &fakeSyncProducer{events: &events}
	session := &fakeSession{ctx: context.Background(), events: &events}
	handler := groupHandler{
		handle: func(context.Context, *sarama.ConsumerMessage) error {
			return NewPermanentError(errors.New("bad payload"))
		},
		dlq: &DLQConfig{Producer: &Producer{p: producer}, Origin: "test-origin"},
	}

	if err := handler.ConsumeClaim(session, &fakeClaim{topic: message.Topic, messages: messages}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(producer.sent) != 1 {
		t.Fatalf("expected exactly one DLQ publish, got %d", len(producer.sent))
	}
	if got := producer.sent[0].Topic; got != "alert.created.v1.dlq" {
		t.Errorf("dlq topic = %q", got)
	}
	if len(session.marked) != 1 || session.marked[0] != message {
		t.Fatalf("marked = %v, want exactly the one message", session.marked)
	}
	if want := []string{"publish", "mark"}; !equalStrings(events, want) {
		t.Fatalf("event order = %v, want %v", events, want)
	}
}

func TestConsumeClaim_DLQPublishFailureDoesNotMarkAndPropagates(t *testing.T) {
	messages := make(chan *sarama.ConsumerMessage, 1)
	message := testMessage()
	messages <- message
	// Deliberately not closed: the loop must return via the publish-error
	// path without ever reading again.

	producer := &fakeSyncProducer{sendErr: errors.New("broker unavailable")}
	session := &fakeSession{ctx: context.Background()}
	handler := groupHandler{
		handle: func(context.Context, *sarama.ConsumerMessage) error {
			return NewPermanentError(errors.New("bad payload"))
		},
		dlq: &DLQConfig{Producer: &Producer{p: producer}, Origin: "test"},
	}

	err := handler.ConsumeClaim(session, &fakeClaim{topic: message.Topic, messages: messages})
	if err == nil {
		t.Fatal("expected the DLQ publish failure to propagate")
	}
	if len(session.marked) != 0 {
		t.Fatalf("expected no mark on DLQ publish failure, got %v", session.marked)
	}
}

func TestConsumeClaim_TransientErrorDoesNotMarkAndPropagatesEvenWithDLQConfigured(t *testing.T) {
	messages := make(chan *sarama.ConsumerMessage, 1)
	message := testMessage()
	messages <- message

	producer := &fakeSyncProducer{}
	session := &fakeSession{ctx: context.Background()}
	transientErr := errors.New("downstream dependency unavailable")
	handler := groupHandler{
		handle: func(context.Context, *sarama.ConsumerMessage) error { return transientErr },
		dlq:    &DLQConfig{Producer: &Producer{p: producer}, Origin: "test"},
	}

	err := handler.ConsumeClaim(session, &fakeClaim{topic: message.Topic, messages: messages})
	if !errors.Is(err, transientErr) {
		t.Fatalf("expected the transient error to propagate unchanged, got %v", err)
	}
	if len(session.marked) != 0 {
		t.Fatalf("expected no mark for a transient error, got %v", session.marked)
	}
	if len(producer.sent) != 0 {
		t.Fatalf("expected the DLQ to never be touched for a transient error, got %d sends", len(producer.sent))
	}
}

func TestConsumeClaim_NilDLQPreservesLegacyBehaviorForPermanentError(t *testing.T) {
	messages := make(chan *sarama.ConsumerMessage, 1)
	message := testMessage()
	messages <- message

	session := &fakeSession{ctx: context.Background()}
	handler := groupHandler{
		handle: func(context.Context, *sarama.ConsumerMessage) error {
			return NewPermanentError(errors.New("bad payload"))
		},
		dlq: nil,
	}

	err := handler.ConsumeClaim(session, &fakeClaim{topic: message.Topic, messages: messages})
	if err == nil {
		t.Fatal("expected a permanent error to still be fatal when DLQ is not configured")
	}
	if len(session.marked) != 0 {
		t.Fatalf("expected no mark, got %v", session.marked)
	}
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
