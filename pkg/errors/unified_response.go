package errors

import (
	"encoding/json"
	"net/http"
	"time"
)

// UnifiedErrorResponse 统一错误响应格式
// 适用于所有服务（Go和Python）的标准化错误响应
type UnifiedErrorResponse struct {
	// 基础字段
	Success   bool   `json:"success"`            // 是否成功（始终为false）
	ErrorCode string `json:"error_code"`         // 错误码（5位数字或字符串）
	Message   string `json:"message"`            // 错误消息（用户可读）
	Timestamp string `json:"timestamp"`          // 时间戳（ISO8601格式）
	
	// 可选字段
	RequestID string                 `json:"request_id,omitempty"` // 请求ID（用于追踪）
	TraceID   string                 `json:"trace_id,omitempty"`   // 链路追踪ID
	Path      string                 `json:"path,omitempty"`       // 请求路径
	Method    string                 `json:"method,omitempty"`     // 请求方法
	Details   map[string]interface{} `json:"details,omitempty"`    // 详细信息
	Stack     string                 `json:"stack,omitempty"`      // 堆栈信息（仅debug模式）
}

// UnifiedSuccessResponse 统一成功响应格式
type UnifiedSuccessResponse struct {
	Success   bool                   `json:"success"`            // 是否成功（始终为true）
	Data      interface{}            `json:"data,omitempty"`     // 响应数据
	Message   string                 `json:"message,omitempty"`  // 可选消息
	Timestamp string                 `json:"timestamp"`          // 时间戳
	RequestID string                 `json:"request_id,omitempty"` // 请求ID
	Meta      map[string]interface{} `json:"meta,omitempty"`     // 元数据
}

// ErrorCodeMapping 错误码映射
var ErrorCodeMapping = map[string]int{
	// 1xxxx - 通用错误
	"10000": http.StatusBadRequest,           // 请求参数错误
	"10001": http.StatusUnauthorized,         // 未授权
	"10002": http.StatusForbidden,            // 无权限
	"10003": http.StatusNotFound,             // 资源不存在
	"10004": http.StatusRequestTimeout,       // 请求超时
	"10005": http.StatusTooManyRequests,      // 请求过多
	"10006": http.StatusInternalServerError,  // 内部错误
	
	// 2xxxx - 业务错误
	"20001": http.StatusBadRequest,           // LLM调用失败
	"20002": http.StatusServiceUnavailable,   // LLM超时
	"20003": http.StatusTooManyRequests,      // LLM限流
	"20004": http.StatusBadRequest,           // Agent执行失败
	"20005": http.StatusBadRequest,           // RAG检索失败
	
	// 3xxxx - 数据错误
	"30001": http.StatusBadRequest,           // 数据验证失败
	"30002": http.StatusNotFound,             // 数据不存在
	"30003": http.StatusConflict,             // 数据冲突
	"30004": http.StatusRequestTimeout,       // 查询超时
	
	// 4xxxx - 服务错误
	"40001": http.StatusServiceUnavailable,   // 服务不可用
	"40002": http.StatusGatewayTimeout,       // 服务超时
	"40003": http.StatusServiceUnavailable,   // 熔断器打开
	
	// 5xxxx - 系统错误
	"50001": http.StatusInternalServerError,  // 系统错误
	"50002": http.StatusInternalServerError,  // 数据库错误
	"50003": http.StatusInternalServerError,  // 缓存错误
	"50004": http.StatusInternalServerError,  // 消息队列错误
}

// NewErrorResponse 创建错误响应
func NewErrorResponse(errorCode, message string) *UnifiedErrorResponse {
	return &UnifiedErrorResponse{
		Success:   false,
		ErrorCode: errorCode,
		Message:   message,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
}

// WithRequestID 添加请求ID
func (e *UnifiedErrorResponse) WithRequestID(requestID string) *UnifiedErrorResponse {
	e.RequestID = requestID
	return e
}

// WithTraceID 添加链路追踪ID
func (e *UnifiedErrorResponse) WithTraceID(traceID string) *UnifiedErrorResponse {
	e.TraceID = traceID
	return e
}

// WithPath 添加请求路径
func (e *UnifiedErrorResponse) WithPath(path string) *UnifiedErrorResponse {
	e.Path = path
	return e
}

// WithMethod 添加请求方法
func (e *UnifiedErrorResponse) WithMethod(method string) *UnifiedErrorResponse {
	e.Method = method
	return e
}

// WithDetails 添加详细信息
func (e *UnifiedErrorResponse) WithDetails(details map[string]interface{}) *UnifiedErrorResponse {
	e.Details = details
	return e
}

// WithStack 添加堆栈信息（仅debug模式）
func (e *UnifiedErrorResponse) WithStack(stack string) *UnifiedErrorResponse {
	e.Stack = stack
	return e
}

// GetHTTPStatus 获取HTTP状态码
func (e *UnifiedErrorResponse) GetHTTPStatus() int {
	if status, ok := ErrorCodeMapping[e.ErrorCode]; ok {
		return status
	}
	return http.StatusInternalServerError
}

// ToJSON 转换为JSON
func (e *UnifiedErrorResponse) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// NewSuccessResponse 创建成功响应
func NewSuccessResponse(data interface{}) *UnifiedSuccessResponse {
	return &UnifiedSuccessResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
}

// WithMessage 添加消息
func (s *UnifiedSuccessResponse) WithMessage(message string) *UnifiedSuccessResponse {
	s.Message = message
	return s
}

// WithRequestID 添加请求ID
func (s *UnifiedSuccessResponse) WithRequestID(requestID string) *UnifiedSuccessResponse {
	s.RequestID = requestID
	return s
}

// WithMeta 添加元数据
func (s *UnifiedSuccessResponse) WithMeta(meta map[string]interface{}) *UnifiedSuccessResponse {
	s.Meta = meta
	return s
}

// ToJSON 转换为JSON
func (s *UnifiedSuccessResponse) ToJSON() ([]byte, error) {
	return json.Marshal(s)
}

// IsRetryable 判断错误是否可重试
func IsRetryable(errorCode string) bool {
	retryableCodes := map[string]bool{
		"10004": true, // 请求超时
		"10005": true, // 请求过多
		"20002": true, // LLM超时
		"20003": true, // LLM限流
		"30004": true, // 查询超时
		"40001": true, // 服务不可用
		"40002": true, // 服务超时
		"40003": true, // 熔断器打开
	}
	return retryableCodes[errorCode]
}

// CommonErrors 常见错误定义
var CommonErrors = struct {
	BadRequest          string
	Unauthorized        string
	Forbidden           string
	NotFound            string
	Timeout             string
	TooManyRequests     string
	InternalServerError string
	ServiceUnavailable  string
	LLMFailed           string
	LLMTimeout          string
	LLMRateLimited      string
	AgentFailed         string
	RAGFailed           string
	DataValidation      string
	DataNotFound        string
	QueryTimeout        string
	CircuitBreakerOpen  string
}{
	BadRequest:          "10000",
	Unauthorized:        "10001",
	Forbidden:           "10002",
	NotFound:            "10003",
	Timeout:             "10004",
	TooManyRequests:     "10005",
	InternalServerError: "10006",
	ServiceUnavailable:  "40001",
	LLMFailed:           "20001",
	LLMTimeout:          "20002",
	LLMRateLimited:      "20003",
	AgentFailed:         "20004",
	RAGFailed:           "20005",
	DataValidation:      "30001",
	DataNotFound:        "30002",
	QueryTimeout:        "30004",
	CircuitBreakerOpen:  "40003",
}

