package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// AuditLogger 审计日志记录器
type AuditLogger struct {
	logger         *log.Helper
	sensitiveFields []string
	skipPaths      []string
}

// AuditLog 审计日志结构
type AuditLog struct {
	Timestamp    time.Time         `json:"timestamp"`
	RequestID    string            `json:"request_id"`
	UserID       string            `json:"user_id"`
	TenantID     string            `json:"tenant_id"`
	Method       string            `json:"method"`
	Path         string            `json:"path"`
	Query        string            `json:"query,omitempty"`
	RequestBody  string            `json:"request_body,omitempty"`
	ResponseCode int               `json:"response_code"`
	DurationMs   int64             `json:"duration_ms"`
	ClientIP     string            `json:"client_ip"`
	UserAgent    string            `json:"user_agent"`
	Error        string            `json:"error,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// AuditConfig 审计配置
type AuditConfig struct {
	Enabled         bool
	SensitivePaths  []string
	SensitiveFields []string
	SkipPaths       []string
}

// NewAuditLogger 创建审计日志记录器
func NewAuditLogger(config *AuditConfig, logger log.Logger) *AuditLogger {
	if config == nil {
		config = &AuditConfig{
			Enabled: true,
			SensitivePaths: []string{
				"/api/v1/conversations",
				"/api/v1/messages",
			},
			SensitiveFields: []string{
				"password", "token", "secret", "key",
				"email", "phone", "id_card",
			},
			SkipPaths: []string{
				"/health",
				"/metrics",
			},
		}
	}

	return &AuditLogger{
		logger:         log.NewHelper(log.With(logger, "module", "audit")),
		sensitiveFields: config.SensitiveFields,
		skipPaths:      config.SkipPaths,
	}
}

// Middleware 审计日志中间件
func (al *AuditLogger) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 跳过不需要审计的路径
		if al.shouldSkip(c.Request.URL.Path) {
			c.Next()
			return
		}

		// 仅审计关键操作
		if !al.shouldAudit(c.Request.Method, c.Request.URL.Path) {
			c.Next()
			return
		}

		start := time.Now()

		// 生成请求 ID（如果没有）
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = generateRequestID()
			c.Set("request_id", requestID)
		}

		// 读取请求体（用于审计）
		var requestBody string
		if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "PATCH" {
			bodyBytes, err := io.ReadAll(c.Request.Body)
			if err == nil {
				c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
				requestBody = string(bodyBytes)

				// PII 脱敏
				requestBody = al.redactSensitiveData(requestBody)

				// 限制长度
				if len(requestBody) > 2000 {
					requestBody = requestBody[:2000] + "... (truncated)"
				}
			}
		}

		// 处理请求
		c.Next()

		// 构建审计日志
		auditLog := AuditLog{
			Timestamp:    start,
			RequestID:    requestID,
			UserID:       c.GetString("user_id"),
			TenantID:     c.GetString("tenant_id"),
			Method:       c.Request.Method,
			Path:         c.Request.URL.Path,
			Query:        c.Request.URL.RawQuery,
			RequestBody:  requestBody,
			ResponseCode: c.Writer.Status(),
			DurationMs:   time.Since(start).Milliseconds(),
			ClientIP:     c.ClientIP(),
			UserAgent:    c.Request.UserAgent(),
			Metadata:     make(map[string]string),
		}

		// 添加额外元数据
		if role := c.GetString("role"); role != "" {
			auditLog.Metadata["role"] = role
		}

		// 记录错误
		if len(c.Errors) > 0 {
			auditLog.Error = c.Errors.String()
		}

		// 写入审计日志
		al.writeAuditLog(&auditLog)
	}
}

// writeAuditLog 写入审计日志
func (al *AuditLogger) writeAuditLog(auditLog *AuditLog) {
	logData, err := json.Marshal(auditLog)
	if err != nil {
		al.logger.Errorf("Failed to marshal audit log: %v", err)
		return
	}

	// 根据状态码决定日志级别
	level := log.LevelInfo
	if auditLog.ResponseCode >= 400 && auditLog.ResponseCode < 500 {
		level = log.LevelWarn
	} else if auditLog.ResponseCode >= 500 {
		level = log.LevelError
	}

	_ = al.logger.Log(level,
		"event", "audit",
		"data", string(logData),
	)
}

// shouldSkip 检查是否应该跳过审计
func (al *AuditLogger) shouldSkip(path string) bool {
	for _, skipPath := range al.skipPaths {
		if strings.HasPrefix(path, skipPath) {
			return true
		}
	}
	return false
}

// shouldAudit 检查是否应该审计
func (al *AuditLogger) shouldAudit(method, path string) bool {
	// 审计所有写操作
	if method != "GET" && method != "HEAD" && method != "OPTIONS" {
		return true
	}

	// 审计敏感读操作
	sensitivePatterns := []string{
		"/api/v1/conversations/",
		"/api/v1/messages/",
	}

	for _, pattern := range sensitivePatterns {
		if strings.Contains(path, pattern) {
			return true
		}
	}

	return false
}

// redactSensitiveData PII 脱敏
func (al *AuditLogger) redactSensitiveData(data string) string {
	// 脱敏规则
	patterns := map[string]*regexp.Regexp{
		// 邮箱
		"email": regexp.MustCompile(`([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})`),
		// 手机号（中国）
		"phone": regexp.MustCompile(`1[3-9]\d{9}`),
		// 身份证号
		"id_card": regexp.MustCompile(`\d{17}[\dXx]`),
		// 银行卡号
		"bank_card": regexp.MustCompile(`\d{16,19}`),
	}

	result := data

	// 邮箱脱敏：user@example.com -> u***@example.com
	result = patterns["email"].ReplaceAllStringFunc(result, func(email string) string {
		parts := strings.Split(email, "@")
		if len(parts) == 2 && len(parts[0]) > 0 {
			return string(parts[0][0]) + "***@" + parts[1]
		}
		return email
	})

	// 手机号脱敏：13812345678 -> 138****5678
	result = patterns["phone"].ReplaceAllStringFunc(result, func(phone string) string {
		if len(phone) == 11 {
			return phone[:3] + "****" + phone[7:]
		}
		return phone
	})

	// 身份证号脱敏：显示前 6 位和后 4 位
	result = patterns["id_card"].ReplaceAllStringFunc(result, func(idCard string) string {
		if len(idCard) == 18 {
			return idCard[:6] + "********" + idCard[14:]
		}
		return idCard
	})

	// 银行卡号脱敏：显示前 4 位和后 4 位
	result = patterns["bank_card"].ReplaceAllStringFunc(result, func(card string) string {
		if len(card) >= 16 {
			return card[:4] + strings.Repeat("*", len(card)-8) + card[len(card)-4:]
		}
		return card
	})

	// JSON 字段脱敏
	for _, field := range al.sensitiveFields {
		// 简单的 JSON 字段脱敏
		fieldPattern := regexp.MustCompile(fmt.Sprintf(`"%s"\s*:\s*"[^"]*"`, field))
		result = fieldPattern.ReplaceAllString(result, fmt.Sprintf(`"%s":"***"`, field))
	}

	return result
}

// generateRequestID 生成请求 ID
func generateRequestID() string {
	return fmt.Sprintf("%d-%d", time.Now().UnixNano(), randInt())
}

// randInt 生成随机整数
func randInt() int {
	return int(time.Now().UnixNano() % 1000000)
}
