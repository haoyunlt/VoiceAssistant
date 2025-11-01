package domain

import (
	"encoding/json"
	"fmt"
	"time"
)

// StreamEvent 流式事件
type StreamEvent struct {
	Type      string                 `json:"type"`       // 事件类型
	Content   string                 `json:"content"`    // 事件内容
	Metadata  map[string]interface{} `json:"metadata"`   // 元数据
	Timestamp time.Time              `json:"timestamp"`  // 时间戳
	Done      bool                   `json:"done"`       // 是否完成
	Error     string                 `json:"error"`      // 错误信息
}

// StreamEventType 流式事件类型
type StreamEventType string

const (
	StreamEventTypeIntent    StreamEventType = "intent"    // 意图识别
	StreamEventTypeStep      StreamEventType = "step"      // 步骤进度
	StreamEventTypeRetrieval StreamEventType = "retrieval" // 检索结果
	StreamEventTypeText      StreamEventType = "text"      // 文本内容
	StreamEventTypeThinking  StreamEventType = "thinking"  // Agent思考
	StreamEventTypeToolCall  StreamEventType = "tool_call" // 工具调用
	StreamEventTypeFinal     StreamEventType = "final"     // 最终结果
	StreamEventTypeError     StreamEventType = "error"     // 错误
)

// NewStreamEvent 创建流式事件
func NewStreamEvent(eventType StreamEventType, content string) *StreamEvent {
	return &StreamEvent{
		Type:      string(eventType),
		Content:   content,
		Metadata:  make(map[string]interface{}),
		Timestamp: time.Now(),
		Done:      false,
	}
}

// WithMetadata 添加元数据
func (e *StreamEvent) WithMetadata(key string, value interface{}) *StreamEvent {
	e.Metadata[key] = value
	return e
}

// WithDone 标记完成
func (e *StreamEvent) WithDone() *StreamEvent {
	e.Done = true
	return e
}

// WithError 添加错误
func (e *StreamEvent) WithError(err error) *StreamEvent {
	e.Type = string(StreamEventTypeError)
	e.Error = err.Error()
	return e
}

// ToJSON 转换为JSON
func (e *StreamEvent) ToJSON() string {
	data, _ := json.Marshal(e)
	return string(data)
}

// ToSSE 转换为SSE格式
func (e *StreamEvent) ToSSE() string {
	return fmt.Sprintf("data: %s\n\n", e.ToJSON())
}

// StreamPipeline 支持流式输出的Pipeline接口
type StreamPipeline interface {
	Pipeline
	// ExecuteStream 流式执行
	ExecuteStream(task *Task, stream chan<- *StreamEvent) error
}

// StreamChannel 流式通道包装
type StreamChannel struct {
	ch      chan *StreamEvent
	timeout time.Duration
	closed  bool
}

// NewStreamChannel 创建流式通道
func NewStreamChannel(bufferSize int, timeout time.Duration) *StreamChannel {
	return &StreamChannel{
		ch:      make(chan *StreamEvent, bufferSize),
		timeout: timeout,
		closed:  false,
	}
}

// Send 发送事件（带超时）
func (s *StreamChannel) Send(event *StreamEvent) error {
	if s.closed {
		return fmt.Errorf("stream channel is closed")
	}

	select {
	case s.ch <- event:
		return nil
	case <-time.After(s.timeout):
		return fmt.Errorf("stream send timeout")
	}
}

// SendSafe 安全发送（忽略错误）
func (s *StreamChannel) SendSafe(event *StreamEvent) {
	_ = s.Send(event)
}

// Channel 获取底层通道
func (s *StreamChannel) Channel() <-chan *StreamEvent {
	return s.ch
}

// Close 关闭通道
func (s *StreamChannel) Close() {
	if !s.closed {
		close(s.ch)
		s.closed = true
	}
}
