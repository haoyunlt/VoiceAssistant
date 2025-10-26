package biz

import (
	"context"

	"github.com/go-kratos/kratos/v2/log"
)

// Document is the document model.
type Document struct {
	ID       string
	Title    string
	Content  string
	TenantID string
	Status   string // pending, indexing, indexed, failed
	FileURL  string
	Metadata map[string]interface{}
}

// DocumentRepo is the document repository interface.
type DocumentRepo interface {
	CreateDocument(ctx context.Context, doc *Document) error
	GetDocument(ctx context.Context, id string) (*Document, error)
	UpdateDocument(ctx context.Context, doc *Document) error
	DeleteDocument(ctx context.Context, id string) error
	ListDocuments(ctx context.Context, tenantID string, page, pageSize int) ([]*Document, error)
}

// DocumentUsecase is the document usecase.
type DocumentUsecase struct {
	repo DocumentRepo
	log  *log.Helper
}

// NewDocumentUsecase creates a new document usecase.
func NewDocumentUsecase(repo DocumentRepo, logger log.Logger) *DocumentUsecase {
	return &DocumentUsecase{
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// UploadDocument uploads a new document.
func (uc *DocumentUsecase) UploadDocument(ctx context.Context, doc *Document) error {
	uc.log.WithContext(ctx).Infof("Uploading document: %s", doc.Title)
	return uc.repo.CreateDocument(ctx, doc)
}
