package biz

import (
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"

	ws "voiceassistant/cmd/conversation-service/internal/websocket"
)

var (
	// AllowedOrigins Origin白名单
	AllowedOrigins = map[string]bool{
		"http://localhost:3000":              true, // 本地开发
		"http://localhost:8080":              true,
		"https://voiceassistant.example.com": true, // 生产域名
		// 可以从环境变量或配置文件加载
	}

	upgrader = websocket.Upgrader{
		ReadBufferSize:  1024,
		WriteBufferSize: 1024,
		CheckOrigin: func(r *http.Request) bool {
			origin := r.Header.Get("Origin")

			// 如果没有Origin头，允许（可能是非浏览器客户端）
			if origin == "" {
				return true
			}

			// 开发模式：检查环境变量
			if os.Getenv("ALLOW_ALL_ORIGINS") == "true" {
				return true
			}

			// 检查白名单
			if AllowedOrigins[origin] {
				return true
			}

			// 支持通配符子域名
			if checkWildcardOrigin(origin) {
				return true
			}

			// 记录被拒绝的Origin
			log.Warnf("Rejected WebSocket connection from origin: %s", origin)
			return false
		},
	}
)

// checkWildcardOrigin 检查通配符Origin（例如 *.example.com）
func checkWildcardOrigin(origin string) bool {
	// 支持的通配符域名
	wildcardDomains := []string{
		".voiceassistant.example.com",
	}

	for _, domain := range wildcardDomains {
		if strings.HasSuffix(origin, domain) {
			return true
		}
	}

	return false
}

// LoadOriginsFromConfig 从配置加载Origin白名单
func LoadOriginsFromConfig(origins []string) {
	for _, origin := range origins {
		AllowedOrigins[origin] = true
	}
}

// WebSocketHandler WebSocket处理器
type WebSocketHandler struct {
	hub            *ws.Hub
	conversationUC *ConversationUsecase
	log            *log.Helper
}

// NewWebSocketHandler 创建WebSocket处理器
func NewWebSocketHandler(
	hub *ws.Hub,
	conversationUC *ConversationUsecase,
	logger log.Logger,
) *WebSocketHandler {
	return &WebSocketHandler{
		hub:            hub,
		conversationUC: conversationUC,
		log:            log.NewHelper(log.With(logger, "module", "ws-handler")),
	}
}

// HandleWebSocket 处理WebSocket连接
func (h *WebSocketHandler) HandleWebSocket(c *gin.Context) {
	// 1. 获取用户信息（从JWT中间件注入）
	userID := c.GetString("user_id")
	if userID == "" {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		return
	}

	// 2. 获取conversation_id和device_id（可选）
	conversationID := c.Query("conversation_id")
	deviceID := c.Query("device_id")

	if conversationID == "" {
		// 如果没有提供conversation_id，可以创建新会话或使用默认会话
		h.log.Warn("No conversation_id provided, using empty session")
	}

	if deviceID == "" {
		deviceID = "default"
	}

	// 3. 升级到WebSocket
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		h.log.Errorf("Failed to upgrade to WebSocket: %v", err)
		return
	}

	// 4. 创建客户端
	clientID := uuid.New().String()
	client := ws.NewClient(
		clientID,
		userID,
		conversationID,
		deviceID,
		conn,
		h.hub,
		h.log,
	)

	// 5. 注册客户端
	h.hub.Register <- client

	// 6. 启动读写goroutine
	go client.WritePump()
	go client.ReadPump()
}

// GetOnlineUsers 获取在线用户数
func (h *WebSocketHandler) GetOnlineUsers(c *gin.Context) {
	count := h.hub.GetClientCount()

	c.JSON(200, gin.H{
		"code":    200,
		"message": "Success",
		"data": gin.H{
			"online_users": count,
		},
	})
}

// GetUserDevices 获取用户的在线设备数
func (h *WebSocketHandler) GetUserDevices(c *gin.Context) {
	userID := c.GetString("user_id")
	if userID == "" {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		return
	}

	count := h.hub.GetUserDeviceCount(userID)

	c.JSON(200, gin.H{
		"code":    200,
		"message": "Success",
		"data": gin.H{
			"user_id":      userID,
			"device_count": count,
		},
	})
}
