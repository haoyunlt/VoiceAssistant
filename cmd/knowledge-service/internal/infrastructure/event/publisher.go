package event

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/segmentio/kafka-go"
)

// EventPublisher Kafka事件发布器
type EventPublisher struct {
	writer *kafka.Writer
}

// EventPublisherConfig 配置
type EventPublisherConfig struct {
	Brokers []string
	Topic   string
}

// NewEventPublisher 创建事件发布器
func NewEventPublisher(config EventPublisherConfig) *EventPublisher {
	writer := &kafka.Writer{
		Addr:         kafka.TCP(config.Brokers...),
		Topic:        config.Topic,
		Balancer:     &kafka.LeastBytes{},
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		Compression:  kafka.Snappy,
	}

	return &EventPublisher{
		writer: writer,
	}
}

// Close 关闭发布器
func (p *EventPublisher) Close() error {
	return p.writer.Close()
}

// Event 领域事件基础结构
type Event struct {
	EventID      string                 `json:"event_id"`
	EventType    string                 `json:"event_type"`
	EventVersion string                 `json:"event_version"`
	AggregateID  string                 `json:"aggregate_id"`
	TenantID     string                 `json:"tenant_id"`
	UserID       string                 `json:"user_id"`
	Timestamp    time.Time              `json:"timestamp"`
	Payload      map[string]interface{} `json:"payload"`
	Metadata     map[string]string      `json:"metadata"`
}

// PublishDocumentUploaded 发布文档上传事件
func (p *EventPublisher) PublishDocumentUploaded(ctx context.Context, doc *DocumentUploadedEvent) error {
	event := Event{
		EventID:      uuid.New().String(),
		EventType:    "document.uploaded",
		EventVersion: "v1",
		AggregateID:  doc.DocumentID,
		TenantID:     doc.TenantID,
		UserID:       doc.UserID,
		Timestamp:    time.Now().UTC(),
		Payload: map[string]interface{}{
			"document_id":       doc.DocumentID,
			"filename":          doc.Filename,
			"file_size":         doc.FileSize,
			"content_type":      doc.ContentType,
			"storage_path":      doc.StoragePath,
			"knowledge_base_id": doc.KnowledgeBaseID,
		},
		Metadata: doc.Metadata,
	}

	return p.publish(ctx, event)
}

// PublishDocumentDeleted 发布文档删除事件
func (p *EventPublisher) PublishDocumentDeleted(ctx context.Context, doc *DocumentDeletedEvent) error {
	event := Event{
		EventID:      uuid.New().String(),
		EventType:    "document.deleted",
		EventVersion: "v1",
		AggregateID:  doc.DocumentID,
		TenantID:     doc.TenantID,
		UserID:       doc.UserID,
		Timestamp:    time.Now().UTC(),
		Payload: map[string]interface{}{
			"document_id":       doc.DocumentID,
			"filename":          doc.Filename,
			"storage_path":      doc.StoragePath,
			"knowledge_base_id": doc.KnowledgeBaseID,
		},
		Metadata: doc.Metadata,
	}

	return p.publish(ctx, event)
}

// PublishDocumentUpdated 发布文档更新事件
func (p *EventPublisher) PublishDocumentUpdated(ctx context.Context, doc *DocumentUpdatedEvent) error {
	event := Event{
		EventID:      uuid.New().String(),
		EventType:    "document.updated",
		EventVersion: "v1",
		AggregateID:  doc.DocumentID,
		TenantID:     doc.TenantID,
		UserID:       doc.UserID,
		Timestamp:    time.Now().UTC(),
		Payload: map[string]interface{}{
			"document_id":       doc.DocumentID,
			"filename":          doc.Filename,
			"storage_path":      doc.StoragePath,
			"knowledge_base_id": doc.KnowledgeBaseID,
			"changes":           doc.Changes,
		},
		Metadata: doc.Metadata,
	}

	return p.publish(ctx, event)
}

// PublishDocumentIndexed 发布文档索引完成事件 (由Indexing Service发布)
func (p *EventPublisher) PublishDocumentIndexed(ctx context.Context, doc *DocumentIndexedEvent) error {
	event := Event{
		EventID:      uuid.New().String(),
		EventType:    "document.indexed",
		EventVersion: "v1",
		AggregateID:  doc.DocumentID,
		TenantID:     doc.TenantID,
		UserID:       doc.UserID,
		Timestamp:    time.Now().UTC(),
		Payload: map[string]interface{}{
			"document_id":        doc.DocumentID,
			"chunks_count":       doc.ChunksCount,
			"vectors_count":      doc.VectorsCount,
			"processing_time_ms": doc.ProcessingTimeMs,
			"status":             doc.Status,
		},
		Metadata: doc.Metadata,
	}

	return p.publish(ctx, event)
}

// publish 发布事件到Kafka
func (p *EventPublisher) publish(ctx context.Context, event Event) error {
	// 序列化事件
	value, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// 发送消息
	message := kafka.Message{
		Key:   []byte(event.AggregateID), // 使用聚合ID作为key，确保同一文档的事件有序
		Value: value,
		Headers: []kafka.Header{
			{Key: "event_type", Value: []byte(event.EventType)},
			{Key: "event_version", Value: []byte(event.EventVersion)},
			{Key: "tenant_id", Value: []byte(event.TenantID)},
		},
		Time: event.Timestamp,
	}

	if err := p.writer.WriteMessages(ctx, message); err != nil {
		return fmt.Errorf("failed to write message to kafka: %w", err)
	}

	return nil
}

// DocumentUploadedEvent 文档上传事件
type DocumentUploadedEvent struct {
	DocumentID      string
	TenantID        string
	UserID          string
	KnowledgeBaseID string
	Filename        string
	FileSize        int64
	ContentType     string
	StoragePath     string
	Metadata        map[string]string
}

// DocumentDeletedEvent 文档删除事件
type DocumentDeletedEvent struct {
	DocumentID      string
	TenantID        string
	UserID          string
	KnowledgeBaseID string
	Filename        string
	StoragePath     string
	Metadata        map[string]string
}

// DocumentUpdatedEvent 文档更新事件
type DocumentUpdatedEvent struct {
	DocumentID      string
	TenantID        string
	UserID          string
	KnowledgeBaseID string
	Filename        string
	StoragePath     string
	Changes         map[string]interface{}
	Metadata        map[string]string
}

// DocumentIndexedEvent 文档索引完成事件
type DocumentIndexedEvent struct {
	DocumentID       string
	TenantID         string
	UserID           string
	ChunksCount      int
	VectorsCount     int
	ProcessingTimeMs int64
	Status           string // "success" or "failed"
	Metadata         map[string]string
}
