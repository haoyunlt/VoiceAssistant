package service

import (
	"context"
	"fmt"

	"voicehelper/cmd/knowledge-service/internal/biz"
	"voicehelper/cmd/knowledge-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// 临时定义，实际应该从proto生成
type CreateKnowledgeBaseRequest struct {
	Name           string
	Description    string
	Type           string
	TenantID       string
	CreatedBy      string
	EmbeddingModel string
}

type KnowledgeBaseResponse struct {
	ID             string
	Name           string
	Description    string
	Type           string
	Status         string
	TenantID       string
	EmbeddingModel string
	DocumentCount  int32
	ChunkCount     int32
	CreatedAt      *timestamppb.Timestamp
}

type UploadDocumentRequest struct {
	KnowledgeBaseID string
	Name            string
	FileName        string
	FileType        string
	FileSize        int64
	FilePath        string
	TenantID        string
	UploadedBy      string
}

type DocumentResponse struct {
	ID              string
	KnowledgeBaseID string
	Name            string
	FileName        string
	FileType        string
	FileSize        int64
	Status          string
	ChunkCount      int32
	CreatedAt       *timestamppb.Timestamp
}

type GetKnowledgeBaseRequest struct {
	ID string
}

type GetDocumentRequest struct {
	ID string
}

type ListKnowledgeBasesRequest struct {
	TenantID string
	Offset   int32
	Limit    int32
}

type ListKnowledgeBasesResponse struct {
	KnowledgeBases []*KnowledgeBaseResponse
	Total          int64
}

// KnowledgeService 知识服务
type KnowledgeService struct {
	kbUC  *biz.KnowledgeBaseUsecase
	docUC *biz.DocumentUsecase
	log   *log.Helper
}

// NewKnowledgeService 创建知识服务
func NewKnowledgeService(
	kbUC *biz.KnowledgeBaseUsecase,
	docUC *biz.DocumentUsecase,
	logger log.Logger,
) *KnowledgeService {
	return &KnowledgeService{
		kbUC:  kbUC,
		docUC: docUC,
		log:   log.NewHelper(logger),
	}
}

// CreateKnowledgeBase 创建知识库
func (s *KnowledgeService) CreateKnowledgeBase(
	ctx context.Context,
	req *CreateKnowledgeBaseRequest,
) (*KnowledgeBaseResponse, error) {
	kb, err := s.kbUC.CreateKnowledgeBase(
		ctx,
		req.Name,
		req.Description,
		domain.KnowledgeBaseType(req.Type),
		req.TenantID,
		req.CreatedBy,
		domain.EmbeddingModel(req.EmbeddingModel),
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to create knowledge base: %v", err)
		return nil, err
	}

	return s.toKnowledgeBaseResponse(kb), nil
}

// GetKnowledgeBase 获取知识库
func (s *KnowledgeService) GetKnowledgeBase(
	ctx context.Context,
	req *GetKnowledgeBaseRequest,
) (*KnowledgeBaseResponse, error) {
	kb, err := s.kbUC.GetKnowledgeBase(ctx, req.ID)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to get knowledge base: %v", err)
		return nil, err
	}

	return s.toKnowledgeBaseResponse(kb), nil
}

// ListKnowledgeBases 列出知识库
func (s *KnowledgeService) ListKnowledgeBases(
	ctx context.Context,
	req *ListKnowledgeBasesRequest,
) (*ListKnowledgeBasesResponse, error) {
	kbs, total, err := s.kbUC.ListKnowledgeBases(
		ctx,
		req.TenantID,
		int(req.Offset),
		int(req.Limit),
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to list knowledge bases: %v", err)
		return nil, err
	}

	responses := make([]*KnowledgeBaseResponse, len(kbs))
	for i, kb := range kbs {
		responses[i] = s.toKnowledgeBaseResponse(kb)
	}

	return &ListKnowledgeBasesResponse{
		KnowledgeBases: responses,
		Total:          total,
	}, nil
}

// UploadDocument 上传文档
// TODO: 待proto生成后实现完整的上传逻辑
func (s *KnowledgeService) UploadDocument(
	ctx context.Context,
	req *UploadDocumentRequest,
) (*DocumentResponse, error) {
	// 暂时返回错误，等proto生成后再实现
	s.log.WithContext(ctx).Warn("UploadDocument not implemented yet, waiting for proto generation")
	return nil, fmt.Errorf("not implemented")
}

// GetDocument 获取文档
func (s *KnowledgeService) GetDocument(
	ctx context.Context,
	req *GetDocumentRequest,
) (*DocumentResponse, error) {
	doc, err := s.docUC.GetDocument(ctx, req.ID)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to get document: %v", err)
		return nil, err
	}

	return s.toDocumentResponse(doc), nil
}

// ProcessDocument 处理文档
// TODO: 待proto生成后实现
func (s *KnowledgeService) ProcessDocument(
	ctx context.Context,
	req *GetDocumentRequest,
	content string,
) (*DocumentResponse, error) {
	s.log.WithContext(ctx).Warn("ProcessDocument not implemented yet")
	return nil, fmt.Errorf("not implemented")
}

// DeleteDocument 删除文档
func (s *KnowledgeService) DeleteDocument(
	ctx context.Context,
	req *GetDocumentRequest,
) error {
	if err := s.docUC.DeleteDocument(ctx, req.ID); err != nil {
		s.log.WithContext(ctx).Errorf("failed to delete document: %v", err)
		return err
	}

	return nil
}

// toKnowledgeBaseResponse 转换为响应对象
func (s *KnowledgeService) toKnowledgeBaseResponse(kb *domain.KnowledgeBase) *KnowledgeBaseResponse {
	return &KnowledgeBaseResponse{
		ID:             kb.ID,
		Name:           kb.Name,
		Description:    kb.Description,
		Type:           string(kb.Type),
		Status:         string(kb.Status),
		TenantID:       kb.TenantID,
		EmbeddingModel: string(kb.EmbeddingModel),
		DocumentCount:  int32(kb.DocumentCount),
		ChunkCount:     int32(kb.ChunkCount),
		CreatedAt:      timestamppb.New(kb.CreatedAt),
	}
}

// toDocumentResponse 转换为响应对象
func (s *KnowledgeService) toDocumentResponse(doc *domain.Document) *DocumentResponse {
	return &DocumentResponse{
		ID:              doc.ID,
		KnowledgeBaseID: doc.KnowledgeBaseID,
		Name:            doc.Name,
		FileName:        doc.FileName,
		FileType:        string(doc.FileType),
		FileSize:        doc.FileSize,
		Status:          string(doc.Status),
		ChunkCount:      int32(doc.ChunkCount),
		CreatedAt:       timestamppb.New(doc.CreatedAt),
	}
}
