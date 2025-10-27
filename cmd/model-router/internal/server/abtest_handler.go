package server

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"
	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/domain"
	"voiceassistant/cmd/model-router/internal/service"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// ABTestHandler A/B测试处理器
type ABTestHandler struct {
	service *service.ModelRouterService
	log     *log.Helper
}

// NewABTestHandler 创建A/B测试处理器
func NewABTestHandler(service *service.ModelRouterService, logger log.Logger) *ABTestHandler {
	return &ABTestHandler{
		service: service,
		log:     log.NewHelper(logger),
	}
}

// RegisterRoutes 注册路由
func (h *ABTestHandler) RegisterRoutes(r *gin.RouterGroup) {
	abtest := r.Group("/abtests")
	{
		abtest.POST("", h.CreateTest)
		abtest.GET("", h.ListTests)
		abtest.GET("/:id", h.GetTest)
		abtest.DELETE("/:id", h.DeleteTest)

		abtest.POST("/:id/start", h.StartTest)
		abtest.POST("/:id/pause", h.PauseTest)
		abtest.POST("/:id/complete", h.CompleteTest)

		abtest.GET("/:id/results", h.GetResults)
		abtest.POST("/:id/metrics", h.RecordMetric)
	}
}

// CreateTestRequest 创建测试请求
type CreateTestRequest struct {
	Name        string            `json:"name" binding:"required"`
	Description string            `json:"description"`
	StartTime   string            `json:"start_time" binding:"required"` // RFC3339格式
	EndTime     string            `json:"end_time" binding:"required"`
	Strategy    string            `json:"strategy"`
	Variants    []*VariantRequest `json:"variants" binding:"required,min=2"`
	CreatedBy   string            `json:"created_by"`
}

// VariantRequest 变体请求
type VariantRequest struct {
	ID          string  `json:"id" binding:"required"`
	Name        string  `json:"name" binding:"required"`
	ModelID     string  `json:"model_id" binding:"required"`
	Weight      float64 `json:"weight" binding:"required,min=0,max=1"`
	Description string  `json:"description"`
}

// CreateTest 创建A/B测试
func (h *ABTestHandler) CreateTest(c *gin.Context) {
	var req CreateTestRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 解析时间
	startTime, err := time.Parse(time.RFC3339, req.StartTime)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid start_time format"})
		return
	}

	endTime, err := time.Parse(time.RFC3339, req.EndTime)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid end_time format"})
		return
	}

	// 转换变体
	variants := make([]*domain.ABVariant, len(req.Variants))
	for i, v := range req.Variants {
		variants[i] = &domain.ABVariant{
			ID:          v.ID,
			Name:        v.Name,
			ModelID:     v.ModelID,
			Weight:      v.Weight,
			Description: v.Description,
		}
	}

	// 创建测试
	testReq := &application.CreateTestRequest{
		Name:        req.Name,
		Description: req.Description,
		StartTime:   startTime,
		EndTime:     endTime,
		Strategy:    req.Strategy,
		Variants:    variants,
		CreatedBy:   req.CreatedBy,
	}

	test, err := h.service.CreateABTest(context.Background(), testReq)
	if err != nil {
		h.log.Errorf("failed to create ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, test)
}

// ListTests 列出所有测试
func (h *ABTestHandler) ListTests(c *gin.Context) {
	// 解析查询参数
	filters := &domain.TestFilters{}

	if status := c.Query("status"); status != "" {
		filters.Status = domain.TestStatus(status)
	}
	if createdBy := c.Query("created_by"); createdBy != "" {
		filters.CreatedBy = createdBy
	}
	if limit := c.Query("limit"); limit != "" {
		if l, err := strconv.Atoi(limit); err == nil {
			filters.Limit = l
		}
	}
	if offset := c.Query("offset"); offset != "" {
		if o, err := strconv.Atoi(offset); err == nil {
			filters.Offset = o
		}
	}

	tests, err := h.service.ListABTests(context.Background(), filters)
	if err != nil {
		h.log.Errorf("failed to list ab tests: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tests": tests,
		"count": len(tests),
	})
}

// GetTest 获取测试详情
func (h *ABTestHandler) GetTest(c *gin.Context) {
	testID := c.Param("id")

	test, err := h.service.GetABTest(context.Background(), testID)
	if err != nil {
		if err == domain.ErrTestNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "test not found"})
			return
		}
		h.log.Errorf("failed to get ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, test)
}

// DeleteTest 删除测试
func (h *ABTestHandler) DeleteTest(c *gin.Context) {
	testID := c.Param("id")

	if err := h.service.DeleteABTest(context.Background(), testID); err != nil {
		if err == domain.ErrTestNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "test not found"})
			return
		}
		h.log.Errorf("failed to delete ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "test deleted successfully"})
}

// StartTest 启动测试
func (h *ABTestHandler) StartTest(c *gin.Context) {
	testID := c.Param("id")

	if err := h.service.StartABTest(context.Background(), testID); err != nil {
		h.log.Errorf("failed to start ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "test started successfully"})
}

// PauseTest 暂停测试
func (h *ABTestHandler) PauseTest(c *gin.Context) {
	testID := c.Param("id")

	if err := h.service.PauseABTest(context.Background(), testID); err != nil {
		h.log.Errorf("failed to pause ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "test paused successfully"})
}

// CompleteTest 完成测试
func (h *ABTestHandler) CompleteTest(c *gin.Context) {
	testID := c.Param("id")

	if err := h.service.CompleteABTest(context.Background(), testID); err != nil {
		h.log.Errorf("failed to complete ab test: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "test completed successfully"})
}

// GetResults 获取测试结果
func (h *ABTestHandler) GetResults(c *gin.Context) {
	testID := c.Param("id")

	results, err := h.service.GetABTestResults(context.Background(), testID)
	if err != nil {
		if err == domain.ErrTestNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "test not found"})
			return
		}
		h.log.Errorf("failed to get ab test results: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"test_id": testID,
		"results": results,
	})
}

// RecordMetricRequest 记录指标请求
type RecordMetricRequest struct {
	VariantID string  `json:"variant_id" binding:"required"`
	UserID    string  `json:"user_id" binding:"required"`
	Success   bool    `json:"success"`
	LatencyMs float64 `json:"latency_ms"`
	Tokens    int64   `json:"tokens"`
	Cost      float64 `json:"cost"`
}

// RecordMetric 记录测试指标
func (h *ABTestHandler) RecordMetric(c *gin.Context) {
	testID := c.Param("id")

	var req RecordMetricRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.service.RecordABTestMetric(
		context.Background(),
		testID,
		req.VariantID,
		req.UserID,
		req.Success,
		req.LatencyMs,
		req.Tokens,
		req.Cost,
	); err != nil {
		h.log.Errorf("failed to record ab test metric: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "metric recorded successfully"})
}

// UnmarshalJSON 自定义反序列化
func (v *VariantRequest) UnmarshalJSON(data []byte) error {
	type Alias VariantRequest
	aux := &struct {
		*Alias
	}{
		Alias: (*Alias)(v),
	}
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	return nil
}
