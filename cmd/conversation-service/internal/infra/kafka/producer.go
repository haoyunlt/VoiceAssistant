package kafka

import (
	"context"
	"encoding/json"
	"time"

	"github.com/segmentio/kafka-go"
)

type Producer struct {
	writer *kafka.Writer
}

func NewProducer(brokers []string, topic string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:         kafka.TCP(brokers...),
			Topic:        topic,
			Balancer:     &kafka.LeastBytes{},
			RequiredAcks: kafka.RequireOne,
			Async:        false,
		},
	}
}

func (p *Producer) PublishEvent(ctx context.Context, event interface{}) error {
	data, err := json.Marshal(event)
	if err != nil {
		return err
	}

	message := kafka.Message{
		Value: data,
		Time:  time.Now(),
	}

	return p.writer.WriteMessages(ctx, message)
}

func (p *Producer) Close() error {
	return p.writer.Close()
}

// Event structures
type ConversationCreatedEvent struct {
	EventID        string    `json:"event_id"`
	EventType      string    `json:"event_type"`
	EventVersion   string    `json:"event_version"`
	ConversationID string    `json:"conversation_id"`
	UserID         string    `json:"user_id"`
	TenantID       string    `json:"tenant_id"`
	Mode           string    `json:"mode"`
	Title          string    `json:"title"`
	Timestamp      time.Time `json:"timestamp"`
}

type MessageSentEvent struct {
	EventID        string    `json:"event_id"`
	EventType      string    `json:"event_type"`
	EventVersion   string    `json:"event_version"`
	ConversationID string    `json:"conversation_id"`
	MessageID      string    `json:"message_id"`
	UserID         string    `json:"user_id"`
	TenantID       string    `json:"tenant_id"`
	Role           string    `json:"role"`
	Content        string    `json:"content"`
	Timestamp      time.Time `json:"timestamp"`
}

type ConversationClosedEvent struct {
	EventID        string    `json:"event_id"`
	EventType      string    `json:"event_type"`
	EventVersion   string    `json:"event_version"`
	ConversationID string    `json:"conversation_id"`
	UserID         string    `json:"user_id"`
	TenantID       string    `json:"tenant_id"`
	Timestamp      time.Time `json:"timestamp"`
}
