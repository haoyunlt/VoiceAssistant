package errors

import (
	"github.com/go-kratos/kratos/v2/errors"
)

// Common error codes
const (
	// Client errors (4xx)
	CodeBadRequest       = 400
	CodeUnauthorized     = 401
	CodeForbidden        = 403
	CodeNotFound         = 404
	CodeConflict         = 409
	CodeValidationFailed = 422
	CodeTooManyRequests  = 429

	// Server errors (5xx)
	CodeInternalServerError = 500
	CodeServiceUnavailable  = 503
	CodeGatewayTimeout      = 504
)

// Common errors
var (
	ErrBadRequest          = errors.BadRequest("BAD_REQUEST", "Bad request")
	ErrUnauthorized        = errors.Unauthorized("UNAUTHORIZED", "Unauthorized")
	ErrForbidden           = errors.Forbidden("FORBIDDEN", "Forbidden")
	ErrNotFound            = errors.NotFound("NOT_FOUND", "Resource not found")
	ErrConflict            = errors.Conflict("CONFLICT", "Resource conflict")
	ErrValidationFailed    = errors.BadRequest("VALIDATION_FAILED", "Validation failed")
	ErrTooManyRequests     = errors.New(CodeTooManyRequests, "TOO_MANY_REQUESTS", "Too many requests")
	ErrInternalServerError = errors.InternalServer("INTERNAL_SERVER_ERROR", "Internal server error")
	ErrServiceUnavailable  = errors.ServiceUnavailable("SERVICE_UNAVAILABLE", "Service unavailable")
	ErrGatewayTimeout      = errors.New(CodeGatewayTimeout, "GATEWAY_TIMEOUT", "Gateway timeout")
)

// NewBadRequest creates a new bad request error.
func NewBadRequest(reason, message string) *errors.Error {
	return errors.BadRequest(reason, message)
}

// NewUnauthorized creates a new unauthorized error.
func NewUnauthorized(reason, message string) *errors.Error {
	return errors.Unauthorized(reason, message)
}

// NewNotFound creates a new not found error.
func NewNotFound(reason, message string) *errors.Error {
	return errors.NotFound(reason, message)
}

// NewInternalServerError creates a new internal server error.
func NewInternalServerError(reason, message string) *errors.Error {
	return errors.InternalServer(reason, message)
}
