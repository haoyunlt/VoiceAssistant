package kafka

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/Shopify/sarama"
)

// EventProducer Kafka事件生产者
type EventProducer struct {
	producer sarama.SyncProducer
	config   *ProducerConfig
}

// ProducerConfig 生产者配置
type ProducerConfig struct {
	Brokers     []string
	Compression string // none, gzip, snappy, lz4, zstd
	MaxRetries  int
	Timeout     time.Duration
}

// NewEventProducer 创建事件生产者
func NewEventProducer(config *ProducerConfig) (*EventProducer, error) {
	saramaConfig := sarama.NewConfig()
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.RequiredAcks = sarama.WaitForAll // 等待所有副本确认
	saramaConfig.Producer.Retry.Max = config.MaxRetries
	saramaConfig.Producer.Timeout = config.Timeout

	// 设置压缩
	switch config.Compression {
	case "gzip":
		saramaConfig.Producer.Compression = sarama.CompressionGZIP
	case "snappy":
		saramaConfig.Producer.Compression = sarama.CompressionSnappy
	case "lz4":
		saramaConfig.Producer.Compression = sarama.CompressionLZ4
	case "zstd":
		saramaConfig.Producer.Compression = sarama.CompressionZSTD
	default:
		saramaConfig.Producer.Compression = sarama.CompressionNone
	}

	// 创建生产者
	producer, err := sarama.NewSyncProducer(config.Brokers, saramaConfig)
	if err != nil {
		return nil, fmt.Errorf("create producer: %w", err)
	}

	return &EventProducer{
		producer: producer,
		config:   config,
	}, nil
}

// PublishEvent 发布事件
func (p *EventProducer) PublishEvent(topic string, event interface{}) error {
	// 序列化事件
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	// 创建消息
	msg := &sarama.ProducerMessage{
		Topic:     topic,
		Value:     sarama.ByteEncoder(eventBytes),
		Timestamp: time.Now(),
	}

	// 发送消息
	partition, offset, err := p.producer.SendMessage(msg)
	if err != nil {
		return fmt.Errorf("send message: %w", err)
	}

	// 记录成功
	_ = partition
	_ = offset

	return nil
}

// PublishEventWithKey 发布带key的事件（用于分区）
func (p *EventProducer) PublishEventWithKey(topic string, key string, event interface{}) error {
	// 序列化事件
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	// 创建消息
	msg := &sarama.ProducerMessage{
		Topic:     topic,
		Key:       sarama.StringEncoder(key),
		Value:     sarama.ByteEncoder(eventBytes),
		Timestamp: time.Now(),
	}

	// 发送消息
	_, _, err = p.producer.SendMessage(msg)
	if err != nil {
		return fmt.Errorf("send message: %w", err)
	}

	return nil
}

// PublishBatch 批量发布事件
func (p *EventProducer) PublishBatch(topic string, events []interface{}) error {
	// 构建消息列表
	messages := make([]*sarama.ProducerMessage, 0, len(events))

	for _, event := range events {
		eventBytes, err := json.Marshal(event)
		if err != nil {
			return fmt.Errorf("marshal event: %w", err)
		}

		msg := &sarama.ProducerMessage{
			Topic:     topic,
			Value:     sarama.ByteEncoder(eventBytes),
			Timestamp: time.Now(),
		}

		messages = append(messages, msg)
	}

	// 批量发送
	err := p.producer.SendMessages(messages)
	if err != nil {
		return fmt.Errorf("send batch messages: %w", err)
	}

	return nil
}

// Close 关闭生产者
func (p *EventProducer) Close() error {
	if p.producer != nil {
		return p.producer.Close()
	}
	return nil
}

// ConversationCreatedEvent 对话创建事件
type ConversationCreatedEvent struct {
	EventType      string    `json:"event_type"`
	ConversationID string    `json:"conversation_id"`
	TenantID       string    `json:"tenant_id"`
	UserID         string    `json:"user_id"`
	Title          string    `json:"title"`
	Mode           string    `json:"mode"`
	CreatedAt      time.Time `json:"created_at"`
}

// MessageSentEvent 消息发送事件
type MessageSentEvent struct {
	EventType      string    `json:"event_type"`
	MessageID      string    `json:"message_id"`
	ConversationID string    `json:"conversation_id"`
	TenantID       string    `json:"tenant_id"`
	UserID         string    `json:"user_id"`
	Role           string    `json:"role"`
	ContentLength  int       `json:"content_length"`
	CreatedAt      time.Time `json:"created_at"`
}

// ConversationArchivedEvent 对话归档事件
type ConversationArchivedEvent struct {
	EventType      string    `json:"event_type"`
	ConversationID string    `json:"conversation_id"`
	TenantID       string    `json:"tenant_id"`
	UserID         string    `json:"user_id"`
	MessageCount   int       `json:"message_count"`
	ArchivedAt     time.Time `json:"archived_at"`
}
