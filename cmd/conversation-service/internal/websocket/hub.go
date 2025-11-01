package websocket

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// Hub WebSocket连接管理中心
type Hub struct {
	// 已注册的客户端
	Clients map[string]*Client

	// 客户端注册
	Register chan *Client

	// 客户端注销
	Unregister chan *Client

	// 广播消息
	Broadcast chan *BroadcastMessage

	// 按用户ID索引的客户端
	UserClients map[string]map[string]*Client

	// 日志
	log *log.Helper

	// 互斥锁
	mu sync.RWMutex

	// 连接限制配置
	maxConnectionsPerUser int
	maxTotalConnections   int
}

// BroadcastMessage 广播消息
type BroadcastMessage struct {
	UserID  string
	Message []byte
	Exclude string // 排除的ClientID
}

// HubConfig WebSocket Hub 配置
type HubConfig struct {
	MaxConnectionsPerUser int
	MaxTotalConnections   int
	BroadcastBufferSize   int
}

// NewHub 创建新的Hub
func NewHub(logger log.Logger, config *HubConfig) *Hub {
	if config == nil {
		config = &HubConfig{
			MaxConnectionsPerUser: 5,     // 单用户最多 5 个连接
			MaxTotalConnections:   10000, // 总连接数限制
			BroadcastBufferSize:   256,
		}
	}

	return &Hub{
		Clients:               make(map[string]*Client),
		Register:              make(chan *Client),
		Unregister:            make(chan *Client),
		Broadcast:             make(chan *BroadcastMessage, config.BroadcastBufferSize),
		UserClients:           make(map[string]map[string]*Client),
		log:                   log.NewHelper(log.With(logger, "module", "ws-hub")),
		maxConnectionsPerUser: config.MaxConnectionsPerUser,
		maxTotalConnections:   config.MaxTotalConnections,
	}
}

// Run 运行Hub
func (h *Hub) Run(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			h.log.Info("Hub shutting down")
			return

		case client := <-h.Register:
			h.registerClient(client)

		case client := <-h.Unregister:
			h.unregisterClient(client)

		case broadcast := <-h.Broadcast:
			h.broadcastToUser(broadcast)
		}
	}
}

// registerClient 注册客户端
func (h *Hub) registerClient(client *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()

	// 检查总连接数限制
	if len(h.Clients) >= h.maxTotalConnections {
		h.log.Warnf("Rejected connection: max total connections reached (%d)", h.maxTotalConnections)
		h.sendConnectionRejected(client, "Server connection limit reached")
		return
	}

	// 检查单用户连接数限制
	if userClients, ok := h.UserClients[client.UserID]; ok {
		if len(userClients) >= h.maxConnectionsPerUser {
			h.log.Warnf("Rejected connection: user %s exceeded max connections (%d)",
				client.UserID, h.maxConnectionsPerUser)

			// 关闭最旧的连接（可选策略：也可以拒绝新连接）
			h.closeOldestConnection(client.UserID)

			// 或者直接拒绝
			// h.sendConnectionRejected(client, "User connection limit reached")
			// return
		}
	}

	// 添加到客户端映射
	h.Clients[client.ID] = client

	// 添加到用户客户端映射
	if _, ok := h.UserClients[client.UserID]; !ok {
		h.UserClients[client.UserID] = make(map[string]*Client)
	}
	h.UserClients[client.UserID][client.ID] = client

	h.log.Infof("WebSocket client registered: client_id=%s, user_id=%s, session_id=%s, device_id=%s",
		client.ID, client.UserID, client.SessionID, client.DeviceID)

	// 发送欢迎消息
	welcomeMsg := map[string]interface{}{
		"type":      MessageTypeWelcome,
		"message":   "Connected to VoiceHelper",
		"client_id": client.ID,
		"timestamp": time.Now().Unix(),
		"connections": map[string]interface{}{
			"current": len(h.UserClients[client.UserID]),
			"max":     h.maxConnectionsPerUser,
		},
	}
	msgBytes, _ := json.Marshal(welcomeMsg)
	client.SendMessage(msgBytes)

	// 通知其他设备
	h.notifyOtherDevices(client, MessageTypeDeviceOnline)
}

// unregisterClient 注销客户端
func (h *Hub) unregisterClient(client *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, ok := h.Clients[client.ID]; ok {
		delete(h.Clients, client.ID)
		close(client.Send)

		// 从用户客户端映射中移除
		if userClients, ok := h.UserClients[client.UserID]; ok {
			delete(userClients, client.ID)
			if len(userClients) == 0 {
				delete(h.UserClients, client.UserID)
			}
		}

		h.log.Infof("WebSocket client unregistered: client_id=%s, user_id=%s",
			client.ID, client.UserID)

		// 通知其他设备
		h.notifyOtherDevices(client, MessageTypeDeviceOffline)
	}
}

// broadcastToUser 广播消息给用户的所有设备
func (h *Hub) broadcastToUser(broadcast *BroadcastMessage) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if userClients, ok := h.UserClients[broadcast.UserID]; ok {
		for clientID, client := range userClients {
			// 跳过排除的客户端
			if clientID == broadcast.Exclude {
				continue
			}

			select {
			case client.Send <- broadcast.Message:
			default:
				h.log.Warnf("Failed to send to client %s", clientID)
			}
		}
	}
}

// notifyOtherDevices 通知用户的其他设备
func (h *Hub) notifyOtherDevices(client *Client, eventType string) {
	notification := map[string]interface{}{
		"type":      eventType,
		"device_id": client.DeviceID,
		"timestamp": time.Now().Unix(),
	}
	msgBytes, _ := json.Marshal(notification)

	h.Broadcast <- &BroadcastMessage{
		UserID:  client.UserID,
		Message: msgBytes,
		Exclude: client.ID,
	}
}

// HandleMessage 处理客户端消息
func (h *Hub) HandleMessage(client *Client, message []byte) {
	var msg Message
	if err := json.Unmarshal(message, &msg); err != nil {
		h.log.Errorf("Invalid message format: %v", err)
		return
	}

	switch msg.Type {
	case MessageTypePing:
		h.handlePing(client)
	case MessageTypeMessage:
		h.handleChatMessage(client, &msg)
	case MessageTypeTyping:
		h.handleTyping(client, &msg)
	default:
		h.log.Warnf("Unknown message type: %s", msg.Type)
	}
}

// handlePing 处理Ping
func (h *Hub) handlePing(client *Client) {
	pongMsg := map[string]interface{}{
		"type":      MessageTypePong,
		"timestamp": time.Now().Unix(),
	}
	msgBytes, _ := json.Marshal(pongMsg)
	client.SendMessage(msgBytes)
}

// handleChatMessage 处理聊天消息
func (h *Hub) handleChatMessage(client *Client, msg *Message) {
	// 这里可以添加保存消息到数据库的逻辑
	h.log.Infof("Chat message from client %s: %s", client.ID, msg.Content)

	// 广播给用户的其他设备
	msgBytes, _ := json.Marshal(msg)
	h.Broadcast <- &BroadcastMessage{
		UserID:  client.UserID,
		Message: msgBytes,
		Exclude: client.ID,
	}
}

// handleTyping 处理输入状态
func (h *Hub) handleTyping(client *Client, msg *Message) {
	typingMsg := map[string]interface{}{
		"type":      MessageTypeTyping,
		"user_id":   client.UserID,
		"device_id": client.DeviceID,
		"is_typing": msg.Data["is_typing"],
		"timestamp": time.Now().Unix(),
	}
	msgBytes, _ := json.Marshal(typingMsg)

	// 广播给用户的其他设备
	h.Broadcast <- &BroadcastMessage{
		UserID:  client.UserID,
		Message: msgBytes,
		Exclude: client.ID,
	}
}

// GetClientCount 获取在线客户端数量
func (h *Hub) GetClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.Clients)
}

// GetUserDeviceCount 获取用户的设备数量
func (h *Hub) GetUserDeviceCount(userID string) int {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if userClients, ok := h.UserClients[userID]; ok {
		return len(userClients)
	}
	return 0
}

// sendConnectionRejected 发送连接拒绝消息
func (h *Hub) sendConnectionRejected(client *Client, reason string) {
	rejectMsg := map[string]interface{}{
		"type":      "connection_rejected",
		"reason":    reason,
		"timestamp": time.Now().Unix(),
	}
	msgBytes, _ := json.Marshal(rejectMsg)
	client.SendMessage(msgBytes)

	// 延迟关闭连接
	go func() {
		time.Sleep(time.Second)
		client.Close()
	}()
}

// closeOldestConnection 关闭最旧的连接（基于连接时间）
func (h *Hub) closeOldestConnection(userID string) {
	if userClients, ok := h.UserClients[userID]; ok {
		var oldestClient *Client
		var oldestTime time.Time

		// 找到最旧的连接
		for _, client := range userClients {
			if oldestClient == nil || client.ConnectedAt.Before(oldestTime) {
				oldestClient = client
				oldestTime = client.ConnectedAt
			}
		}

		if oldestClient != nil {
			h.log.Infof("Closing oldest connection for user %s: client_id=%s",
				userID, oldestClient.ID)

			// 发送通知
			noticeMsg := map[string]interface{}{
				"type":      "connection_replaced",
				"message":   "This connection has been replaced by a newer one",
				"timestamp": time.Now().Unix(),
			}
			msgBytes, _ := json.Marshal(noticeMsg)
			oldestClient.SendMessage(msgBytes)

			// 关闭连接
			go func() {
				time.Sleep(time.Second)
				oldestClient.Close()
			}()
		}
	}
}

// SendToUser 发送消息给用户的所有设备
func (h *Hub) SendToUser(userID string, message []byte) error {
	h.Broadcast <- &BroadcastMessage{
		UserID:  userID,
		Message: message,
	}
	return nil
}

// SendToClient 发送消息给特定客户端
func (h *Hub) SendToClient(clientID string, message []byte) error {
	h.mu.RLock()
	client, ok := h.Clients[clientID]
	h.mu.RUnlock()

	if !ok {
		return ErrClientNotFound
	}

	return client.SendMessage(message)
}
