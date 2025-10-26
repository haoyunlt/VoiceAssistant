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
type DocumentUploadedEvent struct {
	EventID      string    `json:"event_id"`
	EventType    string    `json:"event_type"`
	EventVersion string    `json:"event_version"`
	DocumentID   string    `json:"document_id"`
	UserID       string    `json:"user_id"`
	TenantID     string    `json:"tenant_id"`
	Name         string    `json:"name"`
	ContentType  string    `json:"content_type"`
	SizeBytes    int64     `json:"size_bytes"`
	StoragePath  string    `json:"storage_path"`
	Timestamp    time.Time `json:"timestamp"`
}

type DocumentIndexedEvent struct {
	EventID        string    `json:"event_id"`
	EventType      string    `json:"event_type"`
	EventVersion   string    `json:"event_version"`
	DocumentID     string    `json:"document_id"`
	ChunkCount     int       `json:"chunk_count"`
	VectorCount    int       `json:"vector_count"`
	GraphNodeCount int       `json:"graph_node_count"`
	Timestamp      time.Time `json:"timestamp"`
}

type DocumentDeletedEvent struct {
	EventID    string    `json:"event_id"`
	EventType  string    `json:"event_type"`
	DocumentID string    `json:"document_id"`
	UserID     string    `json:"user_id"`
	TenantID   string    `json:"tenant_id"`
	Timestamp  time.Time `json:"timestamp"`
}
