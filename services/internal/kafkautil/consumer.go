package kafkautil

import (
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"time"
	"unicode/utf8"

	"github.com/IBM/sarama"
)

type MessageHandler func(context.Context, *sarama.ConsumerMessage) error

// PermanentError marks a message-processing error as permanent: the message
// itself can never be processed successfully (e.g. a malformed payload), as
// opposed to a transient error (e.g. a temporarily unavailable downstream
// dependency). Wrap an error returned from a MessageHandler with
// NewPermanentError to route it to the configured DLQ (see WithDLQ) instead
// of blocking the partition indefinitely.
//
// Kafka transport/broker errors are never classified this way by this
// package -- only a handler's own explicit wrapping does. Consume's caller is
// responsible for surfacing transport errors (e.g. via
// sarama.ConsumerError) through the handler in a way that does NOT get
// wrapped in PermanentError, so they remain correctly transient.
type PermanentError struct {
	err error
}

// NewPermanentError wraps err as a permanent, non-retryable failure.
func NewPermanentError(err error) *PermanentError {
	return &PermanentError{err: err}
}

func (e *PermanentError) Error() string {
	if e == nil || e.err == nil {
		return "kafkautil: permanent error"
	}
	return e.err.Error()
}

// Unwrap allows errors.Is/errors.As to see through to the wrapped cause.
func (e *PermanentError) Unwrap() error { return e.err }

// IsPermanent reports whether err (or any error in its chain, including one
// wrapped further with e.g. fmt.Errorf("...: %w", err)) is a PermanentError.
func IsPermanent(err error) bool {
	var permanent *PermanentError
	return errors.As(err, &permanent)
}

// DLQConfig enables dead-letter-queue publishing for permanent failures.
// Construct it with WithDLQ; both fields are required when doing so.
type DLQConfig struct {
	// Producer publishes the DLQ envelope, delivery-confirmed (it uses the
	// same synchronous, acknowledged Producer every other Go service in
	// this repository already uses for its own downstream publishes).
	Producer *Producer
	// Origin identifies which service produced the DLQ entry, e.g.
	// "realtime-gateway".
	Origin string
}

type consumeOptions struct {
	dlq *DLQConfig
}

// Option configures optional Consume behavior. The only Option today is
// WithDLQ; a Consume call with no options behaves exactly as it always has.
type Option func(*consumeOptions)

// WithDLQ enables dead-letter-queue publishing for permanent failures (see
// NewPermanentError). Without this option -- the default, and the only
// behavior that existed before this option did -- every handler error,
// permanent or not, remains fatal to the whole claim: existing callers that
// don't pass WithDLQ are completely unaffected by its existence.
func WithDLQ(cfg DLQConfig) Option {
	return func(o *consumeOptions) {
		o.dlq = &cfg
	}
}

type groupHandler struct {
	handle MessageHandler
	dlq    *DLQConfig
}

func (h groupHandler) Setup(sarama.ConsumerGroupSession) error   { return nil }
func (h groupHandler) Cleanup(sarama.ConsumerGroupSession) error { return nil }

func (h groupHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for {
		select {
		case <-session.Context().Done():
			return session.Context().Err()
		case message, ok := <-claim.Messages():
			if !ok {
				return nil
			}
			err := h.handle(session.Context(), message)
			if err == nil {
				session.MarkMessage(message, "processed")
				continue
			}
			if h.dlq == nil || !IsPermanent(err) {
				// Transient (or DLQ not configured at all): fatal to the
				// claim, message never marked, exactly as before WithDLQ
				// existed. Kafka transport/broker errors always land here,
				// since this package never classifies them as permanent.
				return err
			}
			dlqTopic := message.Topic + ".dlq"
			if publishErr := h.dlq.publish(session.Context(), message, err); publishErr != nil {
				return fmt.Errorf("publish permanent failure to dlq topic %q: %w", dlqTopic, publishErr)
			}
			session.MarkMessage(message, "processed")
		}
	}
}

func (cfg *DLQConfig) publish(ctx context.Context, message *sarama.ConsumerMessage, handlerErr error) error {
	if cfg == nil || cfg.Producer == nil {
		return errors.New("kafkautil: dlq producer not configured")
	}
	envelope := buildDLQEnvelope(message, handlerErr, cfg.Origin)
	keyText, _ := encodeBytes(message.Key)
	return cfg.Producer.PublishJSON(ctx, message.Topic+".dlq", keyText, envelope)
}

type dlqHeader struct {
	Key      string `json:"key"`
	Value    string `json:"value"`
	Encoding string `json:"encoding"`
}

// dlqEnvelope is the structure published to `<source-topic>.dlq`.
type dlqEnvelope struct {
	Origin          string      `json:"origin"`
	ErrorType       string      `json:"error_type"`
	Error           string      `json:"error"`
	FailedAt        string      `json:"failed_at"`
	SourceTopic     string      `json:"source_topic"`
	SourcePartition int32       `json:"source_partition"`
	SourceOffset    int64       `json:"source_offset"`
	SourceTimestamp string      `json:"source_timestamp"`
	Key             string      `json:"key"`
	KeyEncoding     string      `json:"key_encoding"`
	Headers         []dlqHeader `json:"headers"`
	Value           string      `json:"value"`
	ValueEncoding   string      `json:"value_encoding"`
}

func buildDLQEnvelope(message *sarama.ConsumerMessage, handlerErr error, origin string) dlqEnvelope {
	keyText, keyEncoding := encodeBytes(message.Key)
	valueText, valueEncoding := encodeBytes(message.Value)
	headers := make([]dlqHeader, 0, len(message.Headers))
	for _, header := range message.Headers {
		if header == nil {
			continue
		}
		headerValueText, headerValueEncoding := encodeBytes(header.Value)
		headers = append(headers, dlqHeader{
			Key:      string(header.Key),
			Value:    headerValueText,
			Encoding: headerValueEncoding,
		})
	}
	return dlqEnvelope{
		Origin:          origin,
		ErrorType:       fmt.Sprintf("%T", rootCause(handlerErr)),
		Error:           handlerErr.Error(),
		FailedAt:        time.Now().UTC().Format(time.RFC3339Nano),
		SourceTopic:     message.Topic,
		SourcePartition: message.Partition,
		SourceOffset:    message.Offset,
		SourceTimestamp: message.Timestamp.UTC().Format(time.RFC3339Nano),
		Key:             keyText,
		KeyEncoding:     keyEncoding,
		Headers:         headers,
		Value:           valueText,
		ValueEncoding:   valueEncoding,
	}
}

// rootCause walks err's Unwrap chain to the innermost error, for a more
// useful error_type in the DLQ envelope than e.g. "*kafkautil.PermanentError"
// or an intermediate fmt.wrapError.
func rootCause(err error) error {
	for {
		unwrapped := errors.Unwrap(err)
		if unwrapped == nil {
			return err
		}
		err = unwrapped
	}
}

// encodeBytes returns value as UTF-8 text where possible, or base64 when it
// isn't valid UTF-8 -- binary-safe either way, and the second return value
// always says which was used.
func encodeBytes(value []byte) (string, string) {
	if len(value) == 0 {
		return "", "utf-8"
	}
	if utf8.Valid(value) {
		return string(value), "utf-8"
	}
	return base64.StdEncoding.EncodeToString(value), "base64"
}

func Consume(ctx context.Context, brokers []string, groupID string, topics []string, handle MessageHandler, opts ...Option) error {
	var options consumeOptions
	for _, opt := range opts {
		opt(&options)
	}
	cfg, err := NewConfig()
	if err != nil {
		return err
	}
	cfg.Consumer.Group.Rebalance.GroupStrategies = []sarama.BalanceStrategy{sarama.NewBalanceStrategySticky()}
	cfg.Consumer.Offsets.Initial = sarama.OffsetOldest
	cfg.Consumer.Return.Errors = true
	group, err := sarama.NewConsumerGroup(brokers, groupID, cfg)
	if err != nil {
		return err
	}
	defer group.Close()
	handler := groupHandler{handle: handle, dlq: options.dlq}
	for ctx.Err() == nil {
		if err := group.Consume(ctx, topics, handler); err != nil && ctx.Err() == nil {
			return err
		}
	}
	return ctx.Err()
}
