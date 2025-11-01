package websocket

// Message WebSocket消息
type Message struct {
	Type           string                 `json:"type"`             // ping, pong, message, typing, sync, etc.
	Content        string                 `json:"content"`          // 消息内容
	ConversationID string                 `json:"conversation_id"`  // 对话 ID
	ID             string                 `json:"id,omitempty"`     // 消息 ID
	Data           map[string]interface{} `json:"data"`             // 额外数据
	Timestamp      int64                  `json:"timestamp"`        // 时间戳
}

// MessageType 消息类型常量
const (
	// 基础消息类型
	MessageTypePing          = "ping"
	MessageTypePong          = "pong"
	MessageTypeMessage       = "message"
	MessageTypeTyping        = "typing"
	MessageTypeSync          = "sync"
	MessageTypeNotification  = "notification"
	MessageTypeDeviceOnline  = "device_online"
	MessageTypeDeviceOffline = "device_offline"
	MessageTypeWelcome       = "welcome"
	MessageTypeError         = "error"

	// AI 流式响应类型
	MessageTypeAIStreamStart = "ai_stream_start" // AI 流式开始
	MessageTypeAIStreamChunk = "ai_stream_chunk" // AI 流式数据块
	MessageTypeAIStreamEnd   = "ai_stream_end"   // AI 流式结束
	MessageTypeAIStreamError = "ai_stream_error" // AI 流式错误
	MessageTypeAIResponse    = "ai_response"     // AI 非流式响应

	// 工具调用类型
	MessageTypeToolCallStart  = "tool_call_start"  // 工具调用开始
	MessageTypeToolCallResult = "tool_call_result" // 工具调用结果
)
