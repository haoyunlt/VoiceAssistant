package websocket

import (
	"encoding/json"
	"sync"

	"github.com/gorilla/websocket"
)

// Connection WebSocket连接
type Connection struct {
	UserID   string
	TenantID string
	Conn     *websocket.Conn
	Send     chan []byte
}

// Manager WebSocket管理器
type Manager struct {
	// userID -> connections
	connections map[string][]*Connection
	mu          sync.RWMutex

	// 注册连接
	register chan *Connection

	// 注销连接
	unregister chan *Connection
}

// NewManager 创建WebSocket管理器
func NewManager() *Manager {
	m := &Manager{
		connections: make(map[string][]*Connection),
		register:    make(chan *Connection, 100),
		unregister:  make(chan *Connection, 100),
	}

	// 启动管理器
	go m.run()

	return m
}

// run 运行管理器
func (m *Manager) run() {
	for {
		select {
		case conn := <-m.register:
			m.addConnection(conn)
		case conn := <-m.unregister:
			m.removeConnection(conn)
		}
	}
}

// Register 注册连接
func (m *Manager) Register(conn *Connection) {
	// 启动读取协程
	go conn.readPump(m)

	// 启动写入协程
	go conn.writePump()

	// 注册到管理器
	m.register <- conn
}

// Unregister 注销连接
func (m *Manager) Unregister(conn *Connection) {
	m.unregister <- conn
}

// addConnection 添加连接
func (m *Manager) addConnection(conn *Connection) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.connections[conn.UserID] == nil {
		m.connections[conn.UserID] = make([]*Connection, 0)
	}

	m.connections[conn.UserID] = append(m.connections[conn.UserID], conn)
}

// removeConnection 移除连接
func (m *Manager) removeConnection(conn *Connection) {
	m.mu.Lock()
	defer m.mu.Unlock()

	connections := m.connections[conn.UserID]
	for i, c := range connections {
		if c == conn {
			// 移除连接
			m.connections[conn.UserID] = append(connections[:i], connections[i+1:]...)

			// 关闭发送通道
			close(conn.Send)

			// 关闭WebSocket连接
			conn.Conn.Close()

			break
		}
	}

	// 如果用户没有连接了，删除映射
	if len(m.connections[conn.UserID]) == 0 {
		delete(m.connections, conn.UserID)
	}
}

// SendToUser 发送消息给用户
func (m *Manager) SendToUser(userID string, message interface{}) error {
	m.mu.RLock()
	connections := m.connections[userID]
	m.mu.RUnlock()

	if len(connections) == 0 {
		return nil // 用户不在线
	}

	// 序列化消息
	data, err := json.Marshal(message)
	if err != nil {
		return err
	}

	// 发送到所有连接
	for _, conn := range connections {
		select {
		case conn.Send <- data:
		default:
			// 发送通道满，关闭连接
			m.Unregister(conn)
		}
	}

	return nil
}

// BroadcastToTenant 广播消息到租户
func (m *Manager) BroadcastToTenant(tenantID string, message interface{}) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// 序列化消息
	data, err := json.Marshal(message)
	if err != nil {
		return err
	}

	// 遍历所有连接
	for _, connections := range m.connections {
		for _, conn := range connections {
			if conn.TenantID == tenantID {
				select {
				case conn.Send <- data:
				default:
					// 发送通道满，关闭连接
					go m.Unregister(conn)
				}
			}
		}
	}

	return nil
}

// GetOnlineUsers 获取在线用户
func (m *Manager) GetOnlineUsers(tenantID string) []string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	users := make(map[string]bool)

	for userID, connections := range m.connections {
		for _, conn := range connections {
			if conn.TenantID == tenantID {
				users[userID] = true
				break
			}
		}
	}

	result := make([]string, 0, len(users))
	for userID := range users {
		result = append(result, userID)
	}

	return result
}

// GetConnectionCount 获取连接数
func (m *Manager) GetConnectionCount() int {
	m.mu.RLock()
	defer m.mu.RUnlock()

	count := 0
	for _, connections := range m.connections {
		count += len(connections)
	}

	return count
}

// readPump 读取消息
func (conn *Connection) readPump(manager *Manager) {
	defer func() {
		manager.Unregister(conn)
	}()

	for {
		_, message, err := conn.Conn.ReadMessage()
		if err != nil {
			break
		}

		// 处理客户端消息（如心跳）
		_ = message
	}
}

// writePump 写入消息
func (conn *Connection) writePump() {
	for {
		select {
		case message, ok := <-conn.Send:
			if !ok {
				// 通道关闭
				conn.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			// 发送消息
			if err := conn.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		}
	}
}
