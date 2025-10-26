package domain

import "errors"

var (
	// Model errors
	ErrModelNotFound     = errors.New("model not found")
	ErrInvalidModelName  = errors.New("invalid model name")
	ErrInvalidEndpoint   = errors.New("invalid endpoint")
	ErrInvalidMaxTokens  = errors.New("invalid max tokens")
	ErrInvalidPriority   = errors.New("invalid priority")
	ErrInvalidWeight     = errors.New("invalid weight")
	ErrInvalidRateLimit  = errors.New("invalid rate limit")
	ErrModelNotAvailable = errors.New("model not available")

	// Route errors
	ErrNoAvailableModel      = errors.New("no available model")
	ErrAllModelsFailed       = errors.New("all models failed")
	ErrInvalidRoutingStrategy = errors.New("invalid routing strategy")
	ErrCapabilityNotSupported = errors.New("capability not supported")
	ErrRateLimitExceeded     = errors.New("rate limit exceeded")

	// Common errors
	ErrInvalidModelID = errors.New("invalid model id")
	ErrUnauthorized   = errors.New("unauthorized")
)
