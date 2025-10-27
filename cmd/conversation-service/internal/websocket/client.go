package websocket

import (
	"sync"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/gorilla/websocket"
)

const (
	// writeWait 写入超时
	writeWait = 10 * time.Second

	// pongWait Pong超时
	pongWait = 60 * time.Second

	// pingPeriod Ping周期（必须小于pongWait）
	pingPeriod = (pongWait * 9) / 10

	// maxMessageSize 最大消息大小
	maxMessageSize = 512 * 1024 // 512KB
)

// Client WebSocket客户端
type Client struct {
	ID        string
	UserID    string
	SessionID string
	DeviceID  string
	Conn      *websocket.Conn
	Send      chan []byte
	Hub       *Hub
	log       *log.Helper
	mu        sync.Mutex
}

// NewClient 创建新的WebSocket客户端
func NewClient(
	id, userID, sessionID, deviceID string,
	conn *websocket.Conn,
	hub *Hub,
	logger log.Logger,
) *Client {
	return &Client{
		ID:        id,
		UserID:    userID,
		SessionID: sessionID,
		DeviceID:  deviceID,
		Conn:      conn,
		Send:      make(chan []byte, 256),
		Hub:       hub,
		log:       log.NewHelper(log.With(logger, "module", "ws-client", "client_id", id)),
	}
}

// ReadPump 从WebSocket读取消息
func (c *Client) ReadPump() {
	defer func() {
		c.Hub.Unregister <- c
		c.Conn.Close()
	}()

	c.Conn.SetReadDeadline(time.Now().Add(pongWait))
	c.Conn.SetPongHandler(func(string) error {
		c.Conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	c.Conn.SetReadLimit(maxMessageSize)

	for {
		_, message, err := c.Conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err,
				websocket.CloseGoingAway,
				websocket.CloseAbnormalClosure) {
				c.log.Errorf("WebSocket error: %v", err)
			}
			break
		}

		// 处理消息
		c.Hub.HandleMessage(c, message)
	}
}

// WritePump 向WebSocket写入消息
func (c *Client) WritePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.Conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.Send:
			c.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// Hub关闭了通道
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.Conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			// 批量写入队列中的其他消息
			n := len(c.Send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.Send)
			}

			if err := w.Close(); err != nil {
				return
			}

		case <-ticker.C:
			c.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// SendMessage 发送消息给客户端
func (c *Client) SendMessage(message []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	select {
	case c.Send <- message:
		return nil
	default:
		return ErrSendBufferFull
	}
}
