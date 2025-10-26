package events

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/IBM/sarama"
	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/timestamppb"

	eventsv1 "voiceassistant/api/proto/events/v1"
)

// Publisher 事件发布器接口
type Publisher interface {
	// Publish 发布事件
	Publish(ctx context.Context, event *eventsv1.BaseEvent) error

	// PublishBatch 批量发布事件
	PublishBatch(ctx context.Context, events []*eventsv1.BaseEvent) error

	// Close 关闭发布器
	Close() error
}

// KafkaPublisher Kafka 事件发布器
type KafkaPublisher struct {
	producer sarama.SyncProducer
	config   *PublisherConfig
}

// PublisherConfig 发布器配置
type PublisherConfig struct {
	Brokers       []string
	Topic         string
	Partitions    int32
	RetryMax      int
	RequiredAcks  sarama.RequiredAcks
	Compression   sarama.CompressionCodec
	FlushMessages int
	FlushMaxMs    int
}

// DefaultPublisherConfig 默认配置
func DefaultPublisherConfig() *PublisherConfig {
	return &PublisherConfig{
		Brokers:       []string{"localhost:9092"},
		Topic:         "events",
		Partitions:    6,
		RetryMax:      3,
		RequiredAcks:  sarama.WaitForLocal,
		Compression:   sarama.CompressionSnappy,
		FlushMessages: 100,
		FlushMaxMs:    100,
	}
}

// NewKafkaPublisher 创建 Kafka 发布器
func NewKafkaPublisher(config *PublisherConfig) (*KafkaPublisher, error) {
	if config == nil {
		config = DefaultPublisherConfig()
	}

	kafkaConfig := sarama.NewConfig()
	kafkaConfig.Producer.Return.Successes = true
	kafkaConfig.Producer.Return.Errors = true
	kafkaConfig.Producer.RequiredAcks = config.RequiredAcks
	kafkaConfig.Producer.Compression = config.Compression
	kafkaConfig.Producer.Retry.Max = config.RetryMax
	kafkaConfig.Producer.Flush.Messages = config.FlushMessages
	kafkaConfig.Producer.Flush.MaxMessages = config.FlushMaxMs
	kafkaConfig.Version = sarama.V3_6_0_0

	producer, err := sarama.NewSyncProducer(config.Brokers, kafkaConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create kafka producer: %w", err)
	}

	return &KafkaPublisher{
		producer: producer,
		config:   config,
	}, nil
}

// Publish 发布事件
func (p *KafkaPublisher) Publish(ctx context.Context, event *eventsv1.BaseEvent) error {
	// 填充默认值
	if event.EventId == "" {
		event.EventId = uuid.New().String()
	}
	if event.Timestamp == nil {
		event.Timestamp = timestamppb.Now()
	}
	if event.EventVersion == "" {
		event.EventVersion = "v1"
	}

	// 序列化
	value, err := proto.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// 构造消息
	msg := &sarama.ProducerMessage{
		Topic: p.getTopicForEventType(event.EventType),
		Key:   sarama.StringEncoder(event.AggregateId),
		Value: sarama.ByteEncoder(value),
		Headers: []sarama.RecordHeader{
			{Key: []byte("event_type"), Value: []byte(event.EventType)},
			{Key: []byte("tenant_id"), Value: []byte(event.TenantId)},
			{Key: []byte("correlation_id"), Value: []byte(event.CorrelationId)},
		},
		Timestamp: time.Now(),
	}

	// 发送消息
	partition, offset, err := p.producer.SendMessage(msg)
	if err != nil {
		return fmt.Errorf("failed to publish event: %w", err)
	}

	// 记录日志 (可选，使用 logger)
	_ = partition
	_ = offset

	return nil
}

// PublishBatch 批量发布事件
func (p *KafkaPublisher) PublishBatch(ctx context.Context, events []*eventsv1.BaseEvent) error {
	messages := make([]*sarama.ProducerMessage, 0, len(events))

	for _, event := range events {
		// 填充默认值
		if event.EventId == "" {
			event.EventId = uuid.New().String()
		}
		if event.Timestamp == nil {
			event.Timestamp = timestamppb.Now()
		}
		if event.EventVersion == "" {
			event.EventVersion = "v1"
		}

		// 序列化
		value, err := proto.Marshal(event)
		if err != nil {
			return fmt.Errorf("failed to marshal event: %w", err)
		}

		// 构造消息
		msg := &sarama.ProducerMessage{
			Topic: p.getTopicForEventType(event.EventType),
			Key:   sarama.StringEncoder(event.AggregateId),
			Value: sarama.ByteEncoder(value),
			Headers: []sarama.RecordHeader{
				{Key: []byte("event_type"), Value: []byte(event.EventType)},
				{Key: []byte("tenant_id"), Value: []byte(event.TenantId)},
				{Key: []byte("correlation_id"), Value: []byte(event.CorrelationId)},
			},
			Timestamp: time.Now(),
		}

		messages = append(messages, msg)
	}

	// 批量发送
	return p.producer.SendMessages(messages)
}

// Close 关闭发布器
func (p *KafkaPublisher) Close() error {
	return p.producer.Close()
}

// getTopicForEventType 根据事件类型获取 Topic
func (p *KafkaPublisher) getTopicForEventType(eventType string) string {
	// 根据事件类型路由到不同 Topic
	// e.g., "conversation.message.sent" -> "conversation.events"
	//       "document.uploaded" -> "document.events"
	//       "identity.user.registered" -> "identity.events"

	if len(eventType) == 0 {
		return p.config.Topic
	}

	// 简单的前缀匹配
	switch {
	case eventType[:12] == "conversation":
		return "conversation.events"
	case eventType[:8] == "document":
		return "document.events"
	case eventType[:8] == "identity":
		return "identity.events"
	default:
		return p.config.Topic
	}
}

// PublishConversationEvent 发布对话事件的辅助函数
func PublishConversationEvent(
	ctx context.Context,
	publisher Publisher,
	eventType string,
	conversationID, tenantID, userID string,
	payload proto.Message,
	metadata map[string]string,
) error {
	// 包装 payload
	anyPayload, err := anypb.New(payload)
	if err != nil {
		return fmt.Errorf("failed to wrap payload: %w", err)
	}

	// 构造 BaseEvent
	event := &eventsv1.BaseEvent{
		EventId:       uuid.New().String(),
		EventType:     eventType,
		EventVersion:  "v1",
		AggregateId:   conversationID,
		TenantId:      tenantID,
		UserId:        userID,
		Timestamp:     timestamppb.Now(),
		Payload:       anyPayload,
		Metadata:      metadata,
		CorrelationId: getCorrelationID(ctx),
	}

	return publisher.Publish(ctx, event)
}

// PublishDocumentEvent 发布文档事件的辅助函数
func PublishDocumentEvent(
	ctx context.Context,
	publisher Publisher,
	eventType string,
	documentID, tenantID, userID string,
	payload proto.Message,
	metadata map[string]string,
) error {
	// 包装 payload
	anyPayload, err := anypb.New(payload)
	if err != nil {
		return fmt.Errorf("failed to wrap payload: %w", err)
	}

	// 构造 BaseEvent
	event := &eventsv1.BaseEvent{
		EventId:       uuid.New().String(),
		EventType:     eventType,
		EventVersion:  "v1",
		AggregateId:   documentID,
		TenantId:      tenantID,
		UserId:        userID,
		Timestamp:     timestamppb.Now(),
		Payload:       anyPayload,
		Metadata:      metadata,
		CorrelationId: getCorrelationID(ctx),
	}

	return publisher.Publish(ctx, event)
}

// getCorrelationID 从上下文获取关联ID
func getCorrelationID(ctx context.Context) string {
	// 从 context 获取 trace ID 或 request ID
	// 这里简化处理，实际应该从 OpenTelemetry 或类似工具获取
	if correlationID, ok := ctx.Value("correlation_id").(string); ok {
		return correlationID
	}
	return uuid.New().String()
}

// MockPublisher 模拟发布器（用于测试）
type MockPublisher struct {
	Events []*eventsv1.BaseEvent
}

// NewMockPublisher 创建模拟发布器
func NewMockPublisher() *MockPublisher {
	return &MockPublisher{
		Events: make([]*eventsv1.BaseEvent, 0),
	}
}

// Publish 发布事件
func (m *MockPublisher) Publish(ctx context.Context, event *eventsv1.BaseEvent) error {
	m.Events = append(m.Events, event)
	return nil
}

// PublishBatch 批量发布
func (m *MockPublisher) PublishBatch(ctx context.Context, events []*eventsv1.BaseEvent) error {
	m.Events = append(m.Events, events...)
	return nil
}

// Close 关闭
func (m *MockPublisher) Close() error {
	return nil
}

// GetEvents 获取所有事件
func (m *MockPublisher) GetEvents() []*eventsv1.BaseEvent {
	return m.Events
}

// Clear 清空事件
func (m *MockPublisher) Clear() {
	m.Events = make([]*eventsv1.BaseEvent, 0)
}

// PrintEvents 打印事件（调试用）
func (m *MockPublisher) PrintEvents() {
	for i, event := range m.Events {
		fmt.Printf("[Event %d] Type: %s, AggregateID: %s, TenantID: %s\n",
			i+1, event.EventType, event.AggregateId, event.TenantId)

		payloadJSON, _ := json.MarshalIndent(event.Payload, "  ", "  ")
		fmt.Printf("  Payload: %s\n", payloadJSON)
	}
}
