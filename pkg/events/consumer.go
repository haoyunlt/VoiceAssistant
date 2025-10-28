package events

import (
	"context"
	"fmt"
	"log"
	"sync"

	"github.com/IBM/sarama"
	"google.golang.org/protobuf/proto"

	eventsv1 "voicehelper/api/proto/events/v1"
)

// EventHandler 事件处理器接口
type EventHandler interface {
	// Handle 处理事件
	Handle(ctx context.Context, event *eventsv1.BaseEvent) error

	// SupportedEventTypes 支持的事件类型
	SupportedEventTypes() []string
}

// Consumer 事件消费者接口
type Consumer interface {
	// Subscribe 订阅事件
	Subscribe(ctx context.Context, topics []string, handler EventHandler) error

	// Close 关闭消费者
	Close() error
}

// KafkaConsumer Kafka 事件消费者
type KafkaConsumer struct {
	client        sarama.ConsumerGroup
	config        *ConsumerConfig
	handlers      map[string]EventHandler
	handlersMutex sync.RWMutex
	wg            sync.WaitGroup
}

// ConsumerConfig 消费者配置
type ConsumerConfig struct {
	Brokers       []string
	GroupID       string
	Topics        []string
	AutoCommit    bool
	InitialOffset int64 // sarama.OffsetNewest or sarama.OffsetOldest
}

// DefaultConsumerConfig 默认配置
func DefaultConsumerConfig(groupID string) *ConsumerConfig {
	return &ConsumerConfig{
		Brokers:       []string{"localhost:9092"},
		GroupID:       groupID,
		Topics:        []string{"conversation.events", "document.events", "identity.events"},
		AutoCommit:    true,
		InitialOffset: sarama.OffsetNewest,
	}
}

// NewKafkaConsumer 创建 Kafka 消费者
func NewKafkaConsumer(config *ConsumerConfig) (*KafkaConsumer, error) {
	if config == nil {
		return nil, fmt.Errorf("config cannot be nil")
	}

	kafkaConfig := sarama.NewConfig()
	kafkaConfig.Version = sarama.V3_6_0_0
	kafkaConfig.Consumer.Return.Errors = true
	kafkaConfig.Consumer.Offsets.Initial = config.InitialOffset
	kafkaConfig.Consumer.Offsets.AutoCommit.Enable = config.AutoCommit
	kafkaConfig.Consumer.Group.Rebalance.Strategy = sarama.NewBalanceStrategyRoundRobin()

	client, err := sarama.NewConsumerGroup(config.Brokers, config.GroupID, kafkaConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create consumer group: %w", err)
	}

	return &KafkaConsumer{
		client:   client,
		config:   config,
		handlers: make(map[string]EventHandler),
	}, nil
}

// Subscribe 订阅事件
func (c *KafkaConsumer) Subscribe(ctx context.Context, topics []string, handler EventHandler) error {
	// 注册处理器
	c.handlersMutex.Lock()
	for _, eventType := range handler.SupportedEventTypes() {
		c.handlers[eventType] = handler
	}
	c.handlersMutex.Unlock()

	// 启动消费循环
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()

		consumerHandler := &consumerGroupHandler{
			consumer: c,
		}

		for {
			select {
			case <-ctx.Done():
				log.Println("Consumer context cancelled, stopping...")
				return
			default:
				if err := c.client.Consume(ctx, topics, consumerHandler); err != nil {
					log.Printf("Error consuming: %v", err)
					return
				}
			}
		}
	}()

	// 启动错误处理
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		for err := range c.client.Errors() {
			log.Printf("Consumer error: %v", err)
		}
	}()

	return nil
}

// Close 关闭消费者
func (c *KafkaConsumer) Close() error {
	if err := c.client.Close(); err != nil {
		return fmt.Errorf("failed to close consumer: %w", err)
	}
	c.wg.Wait()
	return nil
}

// getHandler 获取事件处理器
func (c *KafkaConsumer) getHandler(eventType string) (EventHandler, bool) {
	c.handlersMutex.RLock()
	defer c.handlersMutex.RUnlock()
	handler, ok := c.handlers[eventType]
	return handler, ok
}

// consumerGroupHandler Sarama ConsumerGroupHandler 实现
type consumerGroupHandler struct {
	consumer *KafkaConsumer
}

// Setup 设置
func (h *consumerGroupHandler) Setup(sarama.ConsumerGroupSession) error {
	return nil
}

// Cleanup 清理
func (h *consumerGroupHandler) Cleanup(sarama.ConsumerGroupSession) error {
	return nil
}

// ConsumeClaim 消费消息
func (h *consumerGroupHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for message := range claim.Messages() {
		if err := h.handleMessage(session.Context(), message); err != nil {
			log.Printf("Failed to handle message: %v", err)
			// 继续处理下一条消息，不要因为一条消息失败而停止
			continue
		}

		// 标记消息已处理
		session.MarkMessage(message, "")
	}
	return nil
}

// handleMessage 处理单条消息
func (h *consumerGroupHandler) handleMessage(ctx context.Context, message *sarama.ConsumerMessage) error {
	// 反序列化事件
	var event eventsv1.BaseEvent
	if err := proto.Unmarshal(message.Value, &event); err != nil {
		return fmt.Errorf("failed to unmarshal event: %w", err)
	}

	// 获取处理器
	handler, ok := h.consumer.getHandler(event.EventType)
	if !ok {
		// 没有注册的处理器，跳过
		log.Printf("No handler registered for event type: %s", event.EventType)
		return nil
	}

	// 调用处理器
	if err := handler.Handle(ctx, &event); err != nil {
		return fmt.Errorf("handler failed: %w", err)
	}

	log.Printf("Successfully handled event: %s (ID: %s)", event.EventType, event.EventId)
	return nil
}

// MultiEventHandler 多事件处理器（可以处理多种事件类型）
type MultiEventHandler struct {
	handlers map[string]func(context.Context, *eventsv1.BaseEvent) error
}

// NewMultiEventHandler 创建多事件处理器
func NewMultiEventHandler() *MultiEventHandler {
	return &MultiEventHandler{
		handlers: make(map[string]func(context.Context, *eventsv1.BaseEvent) error),
	}
}

// Register 注册事件处理函数
func (m *MultiEventHandler) Register(eventType string, fn func(context.Context, *eventsv1.BaseEvent) error) {
	m.handlers[eventType] = fn
}

// Handle 处理事件
func (m *MultiEventHandler) Handle(ctx context.Context, event *eventsv1.BaseEvent) error {
	if fn, ok := m.handlers[event.EventType]; ok {
		return fn(ctx, event)
	}
	return fmt.Errorf("no handler for event type: %s", event.EventType)
}

// SupportedEventTypes 支持的事件类型
func (m *MultiEventHandler) SupportedEventTypes() []string {
	types := make([]string, 0, len(m.handlers))
	for eventType := range m.handlers {
		types = append(types, eventType)
	}
	return types
}

// FunctionHandler 函数式事件处理器
type FunctionHandler struct {
	eventTypes []string
	handleFunc func(context.Context, *eventsv1.BaseEvent) error
}

// NewFunctionHandler 创建函数式处理器
func NewFunctionHandler(
	eventTypes []string,
	fn func(context.Context, *eventsv1.BaseEvent) error,
) *FunctionHandler {
	return &FunctionHandler{
		eventTypes: eventTypes,
		handleFunc: fn,
	}
}

// Handle 处理事件
func (f *FunctionHandler) Handle(ctx context.Context, event *eventsv1.BaseEvent) error {
	return f.handleFunc(ctx, event)
}

// SupportedEventTypes 支持的事件类型
func (f *FunctionHandler) SupportedEventTypes() []string {
	return f.eventTypes
}

// RetryHandler 带重试的事件处理器装饰器
type RetryHandler struct {
	handler    EventHandler
	maxRetries int
	retryDelay func(attempt int) int // 返回毫秒
}

// NewRetryHandler 创建带重试的处理器
func NewRetryHandler(handler EventHandler, maxRetries int) *RetryHandler {
	return &RetryHandler{
		handler:    handler,
		maxRetries: maxRetries,
		retryDelay: func(attempt int) int {
			// 指数退避
			return 100 * (1 << uint(attempt))
		},
	}
}

// Handle 处理事件（带重试）
func (r *RetryHandler) Handle(ctx context.Context, event *eventsv1.BaseEvent) error {
	var err error
	for attempt := 0; attempt <= r.maxRetries; attempt++ {
		err = r.handler.Handle(ctx, event)
		if err == nil {
			return nil
		}

		if attempt < r.maxRetries {
			log.Printf("Retry attempt %d/%d for event %s: %v",
				attempt+1, r.maxRetries, event.EventId, err)

			// 等待
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
				// TODO: 添加延迟
			}
		}
	}
	return fmt.Errorf("failed after %d retries: %w", r.maxRetries, err)
}

// SupportedEventTypes 支持的事件类型
func (r *RetryHandler) SupportedEventTypes() []string {
	return r.handler.SupportedEventTypes()
}

// LoggingHandler 带日志的事件处理器装饰器
type LoggingHandler struct {
	handler EventHandler
}

// NewLoggingHandler 创建带日志的处理器
func NewLoggingHandler(handler EventHandler) *LoggingHandler {
	return &LoggingHandler{handler: handler}
}

// Handle 处理事件（带日志）
func (l *LoggingHandler) Handle(ctx context.Context, event *eventsv1.BaseEvent) error {
	log.Printf("[EventHandler] Processing event: Type=%s, ID=%s, AggregateID=%s",
		event.EventType, event.EventId, event.AggregateId)

	err := l.handler.Handle(ctx, event)

	if err != nil {
		log.Printf("[EventHandler] Failed to process event: %v", err)
	} else {
		log.Printf("[EventHandler] Successfully processed event: ID=%s", event.EventId)
	}

	return err
}

// SupportedEventTypes 支持的事件类型
func (l *LoggingHandler) SupportedEventTypes() []string {
	return l.handler.SupportedEventTypes()
}
