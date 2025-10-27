package domain

import "errors"

var (
	// 测试相关错误
	ErrTestNotFound      = errors.New("ab test not found")
	ErrTestNotActive     = errors.New("ab test not active")
	ErrTestAlreadyExists = errors.New("ab test already exists")
	ErrTestDisabled      = errors.New("ab test disabled")

	// 变体相关错误
	ErrVariantNotFound    = errors.New("variant not found")
	ErrInvalidVariants    = errors.New("invalid variants configuration")
	ErrInvalidWeight      = errors.New("invalid variant weight")
	ErrInvalidTotalWeight = errors.New("variant weights must sum to 1.0")

	// 模型相关错误
	ErrModelNotFound = errors.New("model not found in registry")

	// 时间相关错误
	ErrInvalidTimeRange = errors.New("invalid time range: end time must be after start time")

	// Model validation errors
	ErrInvalidPriority  = errors.New("invalid model priority")
	ErrInvalidRateLimit = errors.New("invalid rate limit")
	ErrInvalidModelName = errors.New("invalid model name")
	ErrInvalidEndpoint  = errors.New("invalid endpoint")
	ErrInvalidMaxTokens = errors.New("invalid max tokens")
)
