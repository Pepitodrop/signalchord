package kafkautil

import (
	"context"
	"encoding/json"
	"errors"

	"github.com/IBM/sarama"
)

type Producer struct{ p sarama.SyncProducer }

func NewProducer(brokers []string) (*Producer, error) {
	cfg, err := NewConfig()
	if err != nil {
		return nil, err
	}
	cfg.Producer.RequiredAcks = sarama.WaitForAll
	cfg.Producer.Return.Successes = true
	cfg.Producer.Idempotent = true
	cfg.Net.MaxOpenRequests = 1
	p, err := sarama.NewSyncProducer(brokers, cfg)
	if err != nil {
		return nil, err
	}
	return &Producer{p: p}, nil
}

func (p *Producer) PublishJSON(ctx context.Context, topic, key string, value any) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	body, err := json.Marshal(value)
	if err != nil {
		return err
	}
	_, _, err = p.p.SendMessage(&sarama.ProducerMessage{Topic: topic, Key: sarama.StringEncoder(key), Value: sarama.ByteEncoder(body)})
	return err
}

func (p *Producer) Close() error {
	if p == nil || p.p == nil {
		return errors.New("producer not initialized")
	}
	return p.p.Close()
}
