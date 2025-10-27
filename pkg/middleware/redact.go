package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"regexp"
	"strings"

	"github.com/gin-gonic/gin"
)

var (
	// 邮箱正则
	emailRegex = regexp.MustCompile(`[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`)
	// 手机号正则（中国）
	phoneRegex = regexp.MustCompile(`1[3-9]\d{9}`)
	// 身份证号正则
	idCardRegex = regexp.MustCompile(`\d{17}[\dXx]`)
	// 银行卡号正则
	bankCardRegex = regexp.MustCompile(`\d{16,19}`)
	// IP地址正则
	ipRegex = regexp.MustCompile(`\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`)
)

// RedactConfig PII脱敏配置
type RedactConfig struct {
	RedactEmail    bool
	RedactPhone    bool
	RedactIDCard   bool
	RedactBankCard bool
	RedactIP       bool
}

// PIIRedact PII脱敏中间件
func PIIRedact(config RedactConfig) gin.HandlerFunc {
	return func(c *gin.Context) {
		// 1. 读取并脱敏请求body
		if c.Request.Body != nil && c.Request.ContentLength > 0 {
			bodyBytes, err := io.ReadAll(c.Request.Body)
			if err == nil {
				// 脱敏
				redactedBody := redactPII(string(bodyBytes), config)
				// 替换body
				c.Request.Body = io.NopCloser(bytes.NewBuffer([]byte(redactedBody)))
			}
		}

		// 2. 脱敏响应
		writer := &redactResponseWriter{
			ResponseWriter: c.Writer,
			config:         config,
		}
		c.Writer = writer

		c.Next()
	}
}

// redactPII 脱敏敏感信息
func redactPII(text string, config RedactConfig) string {
	if config.RedactEmail {
		text = emailRegex.ReplaceAllStringFunc(text, func(email string) string {
			parts := strings.Split(email, "@")
			if len(parts) != 2 {
				return email
			}
			username := parts[0]
			if len(username) <= 2 {
				return "***@" + parts[1]
			}
			return username[:2] + "***@" + parts[1]
		})
	}

	if config.RedactPhone {
		text = phoneRegex.ReplaceAllStringFunc(text, func(phone string) string {
			return phone[:3] + "****" + phone[7:]
		})
	}

	if config.RedactIDCard {
		text = idCardRegex.ReplaceAllStringFunc(text, func(idCard string) string {
			return idCard[:6] + "********" + idCard[14:]
		})
	}

	if config.RedactBankCard {
		text = bankCardRegex.ReplaceAllStringFunc(text, func(card string) string {
			if len(card) < 8 {
				return "****"
			}
			return card[:4] + strings.Repeat("*", len(card)-8) + card[len(card)-4:]
		})
	}

	if config.RedactIP {
		text = ipRegex.ReplaceAllString(text, "***.***.***.**")
	}

	return text
}

// redactResponseWriter 脱敏响应writer
type redactResponseWriter struct {
	gin.ResponseWriter
	config RedactConfig
	body   []byte
}

func (w *redactResponseWriter) Write(data []byte) (int, error) {
	// 尝试解析JSON并脱敏
	var jsonData interface{}
	if err := json.Unmarshal(data, &jsonData); err == nil {
		// 是JSON，递归脱敏
		redactedData := w.redactJSON(jsonData)
		redactedBytes, _ := json.Marshal(redactedData)
		return w.ResponseWriter.Write(redactedBytes)
	}

	// 不是JSON，直接字符串脱敏
	redacted := redactPII(string(data), w.config)
	return w.ResponseWriter.Write([]byte(redacted))
}

func (w *redactResponseWriter) redactJSON(data interface{}) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		result := make(map[string]interface{})
		for key, value := range v {
			// 检查是否是敏感字段
			lowerKey := strings.ToLower(key)
			if strings.Contains(lowerKey, "email") ||
				strings.Contains(lowerKey, "phone") ||
				strings.Contains(lowerKey, "idcard") ||
				strings.Contains(lowerKey, "bankcard") ||
				strings.Contains(lowerKey, "password") {
				if str, ok := value.(string); ok {
					result[key] = redactPII(str, w.config)
					continue
				}
			}
			result[key] = w.redactJSON(value)
		}
		return result

	case []interface{}:
		result := make([]interface{}, len(v))
		for i, item := range v {
			result[i] = w.redactJSON(item)
		}
		return result

	case string:
		return redactPII(v, w.config)

	default:
		return v
	}
}
