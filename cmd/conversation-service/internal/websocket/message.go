package websocket

// Message WebSocket消息
type Message struct {
	Type      string                 `json:"type"`      // ping, pong, message, typing, sync, etc.
	Content   string                 `json:"content"`   // 消息内容
	Data      map[string]interface{} `json:"data"`      // 额外数据
	Timestamp int64                  `json:"timestamp"` // 时间戳
}

// MessageType 消息类型常量
const (
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
)
