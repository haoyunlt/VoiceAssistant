package service

import (
	"context"

	"voiceassistant/cmd/model-router/internal/biz"
	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// 临时定义，实际应该从proto生成
type CreateModelRequest struct {
	Name        string
	DisplayName string
	Provider    string
	Type        string
	Endpoint    string
	APIKey      string
}

type ModelResponse struct {
	ID          string
	Name        string
	DisplayName string
	Provider    string
	Type        string
	Status      string
	Priority    int32
	CreatedAt   *timestamppb.Timestamp
}

type RouteRequestPB struct {
	ModelType            string
	Strategy             string
	RequiredCapabilities []string
}

type RouteResponsePB struct {
	SelectedModel *ModelResponse
	Strategy      string
	Reason        string
}

// ModelRouterService 模型路由服务
type ModelRouterService struct {
	modelUC  *biz.ModelUsecase
	routerUC *biz.RouterUsecase
	log      *log.Helper
}

// NewModelRouterService 创建模型路由服务
func NewModelRouterService(
	modelUC *biz.ModelUsecase,
	routerUC *biz.RouterUsecase,
	logger log.Logger,
) *ModelRouterService {
	return &ModelRouterService{
		modelUC:  modelUC,
		routerUC: routerUC,
		log:      log.NewHelper(logger),
	}
}

// CreateModel 创建模型
func (s *ModelRouterService) CreateModel(
	ctx context.Context,
	req *CreateModelRequest,
) (*ModelResponse, error) {
	model, err := s.modelUC.CreateModel(
		ctx,
		req.Name,
		req.DisplayName,
		domain.ModelProvider(req.Provider),
		domain.ModelType(req.Type),
		req.Endpoint,
		req.APIKey,
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to create model: %v", err)
		return nil, err
	}

	return s.toModelResponse(model), nil
}

// Route 路由请求
func (s *ModelRouterService) Route(
	ctx context.Context,
	req *RouteRequestPB,
) (*RouteResponsePB, error) {
	routeReq := domain.NewRouteRequest(
		domain.ModelType(req.ModelType),
		domain.RoutingStrategy(req.Strategy),
	)
	routeReq.RequiredCapabilities = req.RequiredCapabilities

	result, err := s.routerUC.Route(ctx, routeReq)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to route request: %v", err)
		return nil, err
	}

	return &RouteResponsePB{
		SelectedModel: s.toModelResponse(result.SelectedModel),
		Strategy:      string(result.Strategy),
		Reason:        result.Reason,
	}, nil
}

// toModelResponse 转换为响应对象
func (s *ModelRouterService) toModelResponse(model *domain.Model) *ModelResponse {
	return &ModelResponse{
		ID:          model.ID,
		Name:        model.Name,
		DisplayName: model.DisplayName,
		Provider:    string(model.Provider),
		Type:        string(model.Type),
		Status:      string(model.Status),
		Priority:    int32(model.Priority),
		CreatedAt:   timestamppb.New(model.CreatedAt),
	}
}
