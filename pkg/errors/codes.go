package errors

import (
	"fmt"

	"github.com/go-kratos/kratos/v2/errors"
)

// 错误码规范：
// - 1xxxx: 通用错误（HTTP 4xx）
// - 2xxxx: 业务逻辑错误
// - 3xxxx: 数据访问错误
// - 4xxxx: 外部服务错误
// - 5xxxx: 系统级错误（HTTP 5xx）

// ==================== 通用错误 (10000-19999) ====================

const (
	// 基础错误 (10000-10099)
	CodeBadRequest       = 10000
	CodeUnauthorized     = 10001
	CodeForbidden        = 10002
	CodeNotFound         = 10003
	CodeConflict         = 10004
	CodeValidationFailed = 10005
	CodeTooManyRequests  = 10006
	CodeRequestTimeout   = 10007

	// 参数错误 (10100-10199)
	CodeInvalidParameter   = 10100
	CodeMissingParameter   = 10101
	CodeParameterOutOfRange = 10102
	CodeInvalidFormat      = 10103
)

// ==================== 业务逻辑错误 (20000-29999) ====================

const (
	// 任务相关 (20000-20099)
	CodeTaskNotFound        = 20000
	CodeTaskAlreadyExists   = 20001
	CodeTaskExecutionFailed = 20002
	CodeTaskTimeout         = 20003
	CodeTaskCancelled       = 20004
	CodeInvalidTaskType     = 20005
	CodeTaskQueueFull       = 20006

	// Agent 相关 (20100-20199)
	CodeAgentNotFound       = 20100
	CodeAgentInitFailed     = 20101
	CodeToolNotFound        = 20102
	CodeToolExecutionFailed = 20103
	CodeMemoryNotFound      = 20104
	CodeInvalidAgentMode    = 20105

	// LLM 相关 (20200-20299)
	CodeLLMTimeout          = 20200
	CodeLLMRateLimited      = 20201
	CodeLLMQuotaExceeded    = 20202
	CodeLLMInvalidResponse  = 20203
	CodeModelNotSupported   = 20204
	CodeTokenLimitExceeded  = 20205

	// RAG 相关 (20300-20399)
	CodeRetrievalFailed     = 20300
	CodeEmbeddingFailed     = 20301
	CodeRerankFailed        = 20302
	CodeIndexNotFound       = 20303
	CodeDocumentNotFound    = 20304

	// 语音相关 (20400-20499)
	CodeASRFailed           = 20400
	CodeTTSFailed           = 20401
	CodeVADFailed           = 20402
	CodeAudioFormatInvalid  = 20403
)

// ==================== 数据访问错误 (30000-39999) ====================

const (
	// 数据库错误 (30000-30099)
	CodeDatabaseError       = 30000
	CodeRecordNotFound      = 30001
	CodeDuplicateRecord     = 30002
	CodeConnectionFailed    = 30003
	CodeQueryTimeout        = 30004

	// 缓存错误 (30100-30199)
	CodeCacheError          = 30100
	CodeCacheMiss           = 30101
	CodeCacheExpired        = 30102

	// 向量数据库错误 (30200-30299)
	CodeMilvusError         = 30200
	CodeCollectionNotFound  = 30201
	CodeVectorSearchFailed  = 30202
)

// ==================== 外部服务错误 (40000-49999) ====================

const (
	// 服务调用错误 (40000-40099)
	CodeServiceCallFailed   = 40000
	CodeServiceUnavailable  = 40001
	CodeServiceTimeout      = 40002
	CodeCircuitBreakerOpen  = 40003

	// 第三方服务 (40100-40199)
	CodeOpenAIError         = 40100
	CodeAnthropicError      = 40101
	CodeMinIOError          = 40102
	CodeNacosError          = 40103
	CodeRedisError          = 40104
)

// ==================== 系统错误 (50000-59999) ====================

const (
	// 内部错误 (50000-50099)
	CodeInternalServerError = 50000
	CodeUnknownError        = 50001
	CodeNotImplemented      = 50002
	CodeConfigError         = 50003

	// 资源错误 (50100-50199)
	CodeOutOfMemory         = 50100
	CodeDiskFull            = 50101
	CodeResourceExhausted   = 50102
)

// ==================== 错误构造函数 ====================

// NewBusinessError 创建业务错误（2xxxx）
func NewBusinessError(code int, message string) *errors.Error {
	return errors.New(400, fmt.Sprintf("BIZ_%d", code), message)
}

// NewDataError 创建数据访问错误（3xxxx）
func NewDataError(code int, message string) *errors.Error {
	return errors.New(500, fmt.Sprintf("DATA_%d", code), message)
}

// NewServiceError 创建服务错误（4xxxx）
func NewServiceError(code int, message string) *errors.Error {
	return errors.New(503, fmt.Sprintf("SVC_%d", code), message)
}

// NewSystemError 创建系统错误（5xxxx）
func NewSystemError(code int, message string) *errors.Error {
	return errors.New(500, fmt.Sprintf("SYS_%d", code), message)
}

// ==================== 预定义业务错误 ====================

// Task errors
var (
	ErrTaskNotFound = NewBusinessError(CodeTaskNotFound, "Task not found")
	ErrTaskTimeout  = NewBusinessError(CodeTaskTimeout, "Task execution timeout")
)

// Agent errors
var (
	ErrToolNotFound        = NewBusinessError(CodeToolNotFound, "Tool not found")
	ErrToolExecutionFailed = NewBusinessError(CodeToolExecutionFailed, "Tool execution failed")
	ErrMemoryNotFound      = NewBusinessError(CodeMemoryNotFound, "Memory not found")
)

// LLM errors
var (
	ErrLLMTimeout         = NewBusinessError(CodeLLMTimeout, "LLM request timeout")
	ErrLLMQuotaExceeded   = NewBusinessError(CodeLLMQuotaExceeded, "LLM quota exceeded")
	ErrTokenLimitExceeded = NewBusinessError(CodeTokenLimitExceeded, "Token limit exceeded")
)

// Data errors
var (
	ErrRecordNotFound    = NewDataError(CodeRecordNotFound, "Record not found")
	ErrDuplicateRecord   = NewDataError(CodeDuplicateRecord, "Duplicate record")
	ErrConnectionFailed  = NewDataError(CodeConnectionFailed, "Database connection failed")
)

// Service errors
var (
	ErrServiceUnavailable = NewServiceError(CodeServiceUnavailable, "Service unavailable")
	ErrCircuitBreakerOpen = NewServiceError(CodeCircuitBreakerOpen, "Circuit breaker is open")
)

// ==================== 错误包装函数 ====================

// WrapTaskError 包装任务错误
func WrapTaskError(code int, err error, message string) *errors.Error {
	if message == "" {
		message = err.Error()
	}
	return errors.New(400, fmt.Sprintf("BIZ_%d", code), message).WithCause(err)
}

// WrapDataError 包装数据错误
func WrapDataError(code int, err error, message string) *errors.Error {
	if message == "" {
		message = err.Error()
	}
	return errors.New(500, fmt.Sprintf("DATA_%d", code), message).WithCause(err)
}

// WrapServiceError 包装服务错误
func WrapServiceError(code int, err error, message string) *errors.Error {
	if message == "" {
		message = err.Error()
	}
	return errors.New(503, fmt.Sprintf("SVC_%d", code), message).WithCause(err)
}

// ==================== 错误判断函数 ====================

// IsBusinessError 判断是否为业务错误
func IsBusinessError(err error) bool {
	if e := errors.FromError(err); e != nil {
		code, _ := fmt.Sscanf(e.Reason, "BIZ_%d", new(int))
		return code == 1
	}
	return false
}

// IsDataError 判断是否为数据错误
func IsDataError(err error) bool {
	if e := errors.FromError(err); e != nil {
		code, _ := fmt.Sscanf(e.Reason, "DATA_%d", new(int))
		return code == 1
	}
	return false
}

// IsServiceError 判断是否为服务错误
func IsServiceError(err error) bool {
	if e := errors.FromError(err); e != nil {
		code, _ := fmt.Sscanf(e.Reason, "SVC_%d", new(int))
		return code == 1
	}
	return false
}

// GetErrorCode 获取错误码
func GetErrorCode(err error) int {
	if e := errors.FromError(err); e != nil {
		var code int
		fmt.Sscanf(e.Reason, "BIZ_%d", &code)
		fmt.Sscanf(e.Reason, "DATA_%d", &code)
		fmt.Sscanf(e.Reason, "SVC_%d", &code)
		fmt.Sscanf(e.Reason, "SYS_%d", &code)
		return code
	}
	return 0
}
