package kafkautil

import (
	"context"

	"github.com/IBM/sarama"
)

type MessageHandler func(context.Context, *sarama.ConsumerMessage) error

type groupHandler struct{ handle MessageHandler }

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
			if err := h.handle(session.Context(), message); err != nil {
				return err
			}
			session.MarkMessage(message, "processed")
		}
	}
}

func Consume(ctx context.Context, brokers []string, groupID string, topics []string, handle MessageHandler) error {
	cfg := sarama.NewConfig()
	cfg.Version = sarama.V3_7_0_0
	cfg.Consumer.Group.Rebalance.GroupStrategies = []sarama.BalanceStrategy{sarama.NewBalanceStrategySticky()}
	cfg.Consumer.Offsets.Initial = sarama.OffsetOldest
	cfg.Consumer.Return.Errors = true
	group, err := sarama.NewConsumerGroup(brokers, groupID, cfg)
	if err != nil {
		return err
	}
	defer group.Close()
	for ctx.Err() == nil {
		if err := group.Consume(ctx, topics, groupHandler{handle: handle}); err != nil && ctx.Err() == nil {
			return err
		}
	}
	return ctx.Err()
}
