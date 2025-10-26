package domain

import "errors"

var (
	// KnowledgeBase errors
	ErrKnowledgeBaseNotFound     = errors.New("knowledge base not found")
	ErrInvalidKnowledgeBaseName  = errors.New("invalid knowledge base name")
	ErrInvalidKnowledgeBaseID    = errors.New("invalid knowledge base id")
	ErrInvalidChunkSize          = errors.New("invalid chunk size")
	ErrInvalidChunkOverlap       = errors.New("invalid chunk overlap")
	ErrKnowledgeBaseArchived     = errors.New("knowledge base is archived")

	// Document errors
	ErrDocumentNotFound      = errors.New("document not found")
	ErrInvalidDocumentName   = errors.New("invalid document name")
	ErrInvalidDocumentID     = errors.New("invalid document id")
	ErrInvalidFileName       = errors.New("invalid file name")
	ErrDocumentAlreadyExists = errors.New("document already exists")
	ErrDocumentProcessing    = errors.New("document is processing")

	// Chunk errors
	ErrChunkNotFound       = errors.New("chunk not found")
	ErrInvalidChunkContent = errors.New("invalid chunk content")

	// Common errors
	ErrInvalidTenantID   = errors.New("invalid tenant id")
	ErrInvalidCreatedBy  = errors.New("invalid created by")
	ErrInvalidUploadedBy = errors.New("invalid uploaded by")
	ErrUnauthorized      = errors.New("unauthorized")
	ErrPermissionDenied  = errors.New("permission denied")
)
