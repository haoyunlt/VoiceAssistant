package application

import (
	"context"
	"sync"
	"time"

	"voiceassistant/cmd/model-router/internal/adapter"
	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ModelHealthStatus 模型健康状态
type ModelHealthStatus struct {
	ModelID        string
	Status         string  // "healthy", "degraded", "unhealthy"
	Available      bool
	ResponseTimeMs float64
	LastCheckTime  time.Time
	ConsecutiveFails int
	Message        string
}

// HealthChecker 模型健康检查器
type HealthChecker struct {
	adapterClient  *adapter.AdapterClient
	modelRegistry  domain.ModelRegistry
	healthStatus   map[string]*ModelHealthStatus
	mu             sync.RWMutex
	checkInterval  time.Duration
	maxConsecutiveFails int
	log            *log.Helper
	stopChan       chan struct{}
}

// NewHealthChecker 创建健康检查器
func NewHealthChecker(
	adapterClient *adapter.AdapterClient,
	modelRegistry domain.ModelRegistry,
	checkInterval time.Duration,
	logger log.Logger,
) *HealthChecker {
	return &HealthChecker{
		adapterClient:       adapterClient,
		modelRegistry:       modelRegistry,
		healthStatus:        make(map[string]*ModelHealthStatus),
		checkInterval:       checkInterval,
		maxConsecutiveFails: 3,
		log:                 log.NewHelper(logger),
		stopChan:            make(chan struct{}),
	}
}

// Start 启动健康检查
func (hc *HealthChecker) Start(ctx context.Context) {
	hc.log.Info("Starting health checker")

	// 立即执行一次检查
	hc.checkAllModels(ctx)

	// 定期检查
	ticker := time.NewTicker(hc.checkInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			hc.checkAllModels(ctx)
		case <-hc.stopChan:
			hc.log.Info("Health checker stopped")
			return
		case <-ctx.Done():
			hc.log.Info("Health checker context cancelled")
			return
		}
	}
}

// Stop 停止健康检查
func (hc *HealthChecker) Stop() {
	close(hc.stopChan)
}

// checkAllModels 检查所有模型
func (hc *HealthChecker) checkAllModels(ctx context.Context) {
	hc.log.Info("Checking health of all models")

	models := hc.modelRegistry.ListModels()
	if len(models) == 0 {
		hc.log.Warn("No models registered")
		return
	}

	// 提取模型名称
	modelNames := make([]string, 0, len(models))
	for _, model := range models {
		modelNames = append(modelNames, model.Name)
	}

	// 批量健康检查
	checkCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	results := hc.adapterClient.BatchHealthCheck(checkCtx, modelNames)

	// 更新健康状态
	hc.mu.Lock()
	defer hc.mu.Unlock()

	for modelID, result := range results {
		oldStatus, exists := hc.healthStatus[modelID]

		newStatus := &ModelHealthStatus{
			ModelID:        modelID,
			Status:         result.Status,
			Available:      result.Available,
			ResponseTimeMs: result.ResponseTimeMs,
			LastCheckTime:  time.Now(),
			Message:        result.Message,
		}

		if !result.Available {
			// 累计失败次数
			if exists {
				newStatus.ConsecutiveFails = oldStatus.ConsecutiveFails + 1
			} else {
				newStatus.ConsecutiveFails = 1
			}
		} else {
			// 重置失败次数
			newStatus.ConsecutiveFails = 0
		}

		hc.healthStatus[modelID] = newStatus

		// 如果连续失败超过阈值，标记为不可用
		if newStatus.ConsecutiveFails >= hc.maxConsecutiveFails {
			hc.log.Warnf(
				"Model %s has failed %d consecutive health checks, marking as unavailable",
				modelID,
				newStatus.ConsecutiveFails,
			)
			// 更新模型注册表中的可用性
			hc.modelRegistry.UpdateModelAvailability(modelID, false)
		} else if newStatus.Available && exists && oldStatus.ConsecutiveFails >= hc.maxConsecutiveFails {
			// 如果之前标记为不可用，现在恢复了，更新注册表
			hc.log.Infof("Model %s has recovered, marking as available", modelID)
			hc.modelRegistry.UpdateModelAvailability(modelID, true)
		}

		hc.log.Infof(
			"Model %s health: %s (response_time: %.0fms, consecutive_fails: %d)",
			modelID,
			newStatus.Status,
			newStatus.ResponseTimeMs,
			newStatus.ConsecutiveFails,
		)
	}
}

// GetHealthStatus 获取指定模型的健康状态
func (hc *HealthChecker) GetHealthStatus(modelID string) (*ModelHealthStatus, bool) {
	hc.mu.RLock()
	defer hc.mu.RUnlock()

	status, exists := hc.healthStatus[modelID]
	return status, exists
}

// GetAllHealthStatus 获取所有模型的健康状态
func (hc *HealthChecker) GetAllHealthStatus() map[string]*ModelHealthStatus {
	hc.mu.RLock()
	defer hc.mu.RUnlock()

	// 返回副本
	result := make(map[string]*ModelHealthStatus)
	for k, v := range hc.healthStatus {
		statusCopy := *v
		result[k] = &statusCopy
	}

	return result
}

// IsModelHealthy 检查模型是否健康
func (hc *HealthChecker) IsModelHealthy(modelID string) bool {
	hc.mu.RLock()
	defer hc.mu.RUnlock()

	status, exists := hc.healthStatus[modelID]
	if !exists {
		// 未检查过，默认认为健康
		return true
	}

	return status.Available && status.ConsecutiveFails < hc.maxConsecutiveFails
}

// GetHealthyModels 获取所有健康的模型
func (hc *HealthChecker) GetHealthyModels() []string {
	hc.mu.RLock()
	defer hc.mu.RUnlock()

	healthy := make([]string, 0)
	for modelID, status := range hc.healthStatus {
		if status.Available && status.ConsecutiveFails < hc.maxConsecutiveFails {
			healthy = append(healthy, modelID)
		}
	}

	return healthy
}

// GetHealthSummary 获取健康摘要
func (hc *HealthChecker) GetHealthSummary() map[string]interface{} {
	hc.mu.RLock()
	defer hc.mu.RUnlock()

	totalModels := len(hc.healthStatus)
	healthyCount := 0
	degradedCount := 0
	unhealthyCount := 0

	for _, status := range hc.healthStatus {
		switch status.Status {
		case "healthy":
			healthyCount++
		case "degraded":
			degradedCount++
		case "unhealthy":
			unhealthyCount++
		}
	}

	return map[string]interface{}{
		"total_models":    totalModels,
		"healthy_count":   healthyCount,
		"degraded_count":  degradedCount,
		"unhealthy_count": unhealthyCount,
		"last_check_time": time.Now(),
	}
}
