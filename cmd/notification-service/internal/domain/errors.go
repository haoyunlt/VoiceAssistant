package domain

import "errors"

var (
	// Notification errors
	ErrNotificationNotFound = errors.New("notification not found")
	ErrInvalidRecipient     = errors.New("invalid recipient")
	ErrMissingContent       = errors.New("missing content or template")
	ErrNotificationSent     = errors.New("notification already sent")
	ErrMaxRetriesExceeded   = errors.New("max retries exceeded")

	// Template errors
	ErrTemplateNotFound       = errors.New("template not found")
	ErrInvalidTemplateName    = errors.New("invalid template name")
	ErrInvalidTemplateContent = errors.New("invalid template content")
	ErrTemplateNotActive      = errors.New("template not active")

	// Provider errors
	ErrProviderNotFound    = errors.New("provider not found")
	ErrProviderUnavailable = errors.New("provider unavailable")
	ErrSendFailed          = errors.New("send failed")

	// Common errors
	ErrInvalidChannel = errors.New("invalid channel")
	ErrUnauthorized   = errors.New("unauthorized")
)
