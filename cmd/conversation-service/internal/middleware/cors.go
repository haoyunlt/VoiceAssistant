package middleware

import (
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// CORSConfig CORS 配置
type CORSConfig struct {
	AllowedOrigins   []string
	AllowedMethods   []string
	AllowedHeaders   []string
	ExposedHeaders   []string
	AllowCredentials bool
	MaxAge           int
}

// CORSManager CORS 管理器
type CORSManager struct {
	config *CORSConfig
	logger *log.Helper
}

// NewCORSManager 创建 CORS 管理器
func NewCORSManager(config *CORSConfig, logger log.Logger) *CORSManager {
	if config == nil {
		// 默认配置（生产环境应该更严格）
		config = &CORSConfig{
			AllowedOrigins: []string{
				"http://localhost:3000",
				"http://localhost:3001",
				"https://app.voicehelper.com",
			},
			AllowedMethods: []string{
				"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS",
			},
			AllowedHeaders: []string{
				"Content-Type",
				"Authorization",
				"X-Request-ID",
				"X-Idempotency-Key",
				"X-Tenant-ID",
				"X-User-ID",
			},
			ExposedHeaders: []string{
				"X-RateLimit-Limit",
				"X-RateLimit-Remaining",
				"X-RateLimit-Reset",
				"X-Request-ID",
			},
			AllowCredentials: true,
			MaxAge:           3600,
		}
	}

	return &CORSManager{
		config: config,
		logger: log.NewHelper(log.With(logger, "module", "cors")),
	}
}

// Middleware CORS 中间件
func (cm *CORSManager) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.Request.Header.Get("Origin")

		// 检查 origin 是否在白名单中
		if origin != "" && cm.isAllowedOrigin(origin) {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
		} else if origin != "" {
			// 记录未授权的 origin
			cm.logger.Warnf("Blocked CORS request from unauthorized origin: %s", origin)
		}

		// 设置其他 CORS 头
		if cm.config.AllowCredentials {
			c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		}

		// 处理预检请求
		if c.Request.Method == "OPTIONS" {
			c.Writer.Header().Set("Access-Control-Allow-Methods", strings.Join(cm.config.AllowedMethods, ", "))
			c.Writer.Header().Set("Access-Control-Allow-Headers", strings.Join(cm.config.AllowedHeaders, ", "))
			c.Writer.Header().Set("Access-Control-Max-Age", fmt.Sprintf("%d", cm.config.MaxAge))

			c.AbortWithStatus(204)
			return
		}

		// 设置暴露的头
		if len(cm.config.ExposedHeaders) > 0 {
			c.Writer.Header().Set("Access-Control-Expose-Headers", strings.Join(cm.config.ExposedHeaders, ", "))
		}

		c.Next()
	}
}

// isAllowedOrigin 检查 origin 是否允许
func (cm *CORSManager) isAllowedOrigin(origin string) bool {
	for _, allowed := range cm.config.AllowedOrigins {
		// 支持通配符（例如：*.example.com）
		if allowed == "*" {
			return true
		}

		// 精确匹配
		if allowed == origin {
			return true
		}

		// 通配符匹配
		if strings.HasPrefix(allowed, "*.") {
			domain := strings.TrimPrefix(allowed, "*.")
			if strings.HasSuffix(origin, domain) {
				return true
			}
		}
	}

	return false
}

// AddAllowedOrigin 动态添加允许的 origin
func (cm *CORSManager) AddAllowedOrigin(origin string) {
	for _, existing := range cm.config.AllowedOrigins {
		if existing == origin {
			return
		}
	}
	cm.config.AllowedOrigins = append(cm.config.AllowedOrigins, origin)
	cm.logger.Infof("Added allowed origin: %s", origin)
}

// RemoveAllowedOrigin 动态移除允许的 origin
func (cm *CORSManager) RemoveAllowedOrigin(origin string) {
	for i, existing := range cm.config.AllowedOrigins {
		if existing == origin {
			cm.config.AllowedOrigins = append(
				cm.config.AllowedOrigins[:i],
				cm.config.AllowedOrigins[i+1:]...,
			)
			cm.logger.Infof("Removed allowed origin: %s", origin)
			return
		}
	}
}

// GetAllowedOrigins 获取允许的 origins 列表
func (cm *CORSManager) GetAllowedOrigins() []string {
	return cm.config.AllowedOrigins
}
