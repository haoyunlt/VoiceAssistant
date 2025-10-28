package server

import (
	"voiceassistant/cmd/model-router/internal/service"

	"github.com/go-kratos/kratos/v2/log"
)

// ABTestHandler A/B测试处理器（简化版）
type ABTestHandler struct {
	service *service.ModelRouterService
	logger  log.Logger
}

// NewABTestHandler 创建A/B测试处理器
func NewABTestHandler(service *service.ModelRouterService, logger log.Logger) *ABTestHandler {
	return &ABTestHandler{
		service: service,
		logger:  logger,
	}
}
