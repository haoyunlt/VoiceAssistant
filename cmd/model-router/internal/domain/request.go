package domain

import (
	"encoding/json"
	"time"
)

// ModelRequest 模型请求
type ModelRequest struct {
	RequestID       string                 `json:"request_id"`
	TenantID        string                 `json:"tenant_id"`
	UserID          string                 `json:"user_id"`
	ModelID         string                 `json:"model_id"`
	ModelName       string                 `json:"model_name"`
	Provider        string                 `json:"provider"`
	RequestTime     time.Time              `json:"request_time"`
	RequestType     string                 `json:"request_type"` // chat, embedding, etc.
	Stream          bool                   `json:"stream"`
	RoutingStrategy string                 `json:"routing_strategy"`
	FallbackUsed    bool                   `json:"fallback_used"`
	ABTestVariant   string                 `json:"ab_test_variant"`
	Metadata        map[string]interface{} `json:"metadata"`
}

// MetadataJSON 转换 metadata 为 JSON 字符串
func (r *ModelRequest) MetadataJSON() string {
	if r.Metadata == nil {
		return "{}"
	}
	data, _ := json.Marshal(r.Metadata)
	return string(data)
}

// ModelResponse 模型响应
type ModelResponse struct {
	Success          bool    `json:"success"`
	ErrorMessage     string  `json:"error_message,omitempty"`
	ErrorCode        string  `json:"error_code,omitempty"`
	PromptTokens     int     `json:"prompt_tokens"`
	CompletionTokens int     `json:"completion_tokens"`
	TotalTokens      int     `json:"total_tokens"`
	CostUSD          float64 `json:"cost_usd"`
}
