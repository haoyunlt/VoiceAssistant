package resilience

import (
	"context"
	"errors"
	"sync"
	"time"
)

// DegradationLevel 降级级别
type DegradationLevel int

const (
	// LevelNormal 正常级别
	LevelNormal DegradationLevel = iota
	// LevelPartial 部分降级
	LevelPartial
	// LevelFull 完全降级
	LevelFull
)

// String 返回降级级别字符串
func (l DegradationLevel) String() string {
	switch l {
	case LevelNormal:
		return "normal"
	case LevelPartial:
		return "partial"
	case LevelFull:
		return "full"
	default:
		return "unknown"
	}
}

// DegradationManager 降级管理器
type DegradationManager struct {
	mu               sync.RWMutex
	level            DegradationLevel
	degradedFeatures map[string]bool // 降级的功能
	lastUpdate       time.Time
	config           DegradationConfig
	metrics          DegradationMetrics
}

// DegradationConfig 降级配置
type DegradationConfig struct {
	// AutoDegrade 是否自动降级
	AutoDegrade bool
	// ErrorRateThreshold 错误率阈值（触发降级）
	ErrorRateThreshold float64
	// LatencyThreshold 延迟阈值（触发降级）
	LatencyThreshold time.Duration
	// RecoveryThreshold 恢复阈值
	RecoveryThreshold float64
	// CheckInterval 检查间隔
	CheckInterval time.Duration
}

// DegradationMetrics 降级指标
type DegradationMetrics struct {
	TotalRequests    int64
	FailedRequests   int64
	DegradedRequests int64
	ErrorRate        float64
	AvgLatency       time.Duration
}

// NewDegradationManager 创建降级管理器
func NewDegradationManager(config DegradationConfig) *DegradationManager {
	return &DegradationManager{
		level:            LevelNormal,
		degradedFeatures: make(map[string]bool),
		lastUpdate:       time.Now(),
		config:           config,
	}
}

// ShouldDegrade 判断是否应该降级
func (dm *DegradationManager) ShouldDegrade(feature string) bool {
	dm.mu.RLock()
	defer dm.mu.RUnlock()

	// 检查全局降级级别
	if dm.level == LevelFull {
		return true
	}

	// 检查特定功能是否降级
	if degraded, ok := dm.degradedFeatures[feature]; ok && degraded {
		return true
	}

	return false
}

// DegradeFeature 降级特定功能
func (dm *DegradationManager) DegradeFeature(feature string, level DegradationLevel) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	dm.degradedFeatures[feature] = true
	dm.lastUpdate = time.Now()

	// 如果需要，更新全局级别
	if level > dm.level {
		dm.level = level
	}
}

// RecoverFeature 恢复特定功能
func (dm *DegradationManager) RecoverFeature(feature string) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	delete(dm.degradedFeatures, feature)
	dm.lastUpdate = time.Now()

	// 如果没有降级功能，恢复正常
	if len(dm.degradedFeatures) == 0 {
		dm.level = LevelNormal
	}
}

// SetLevel 设置全局降级级别
func (dm *DegradationManager) SetLevel(level DegradationLevel) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	dm.level = level
	dm.lastUpdate = time.Now()
}

// GetLevel 获取当前降级级别
func (dm *DegradationManager) GetLevel() DegradationLevel {
	dm.mu.RLock()
	defer dm.mu.RUnlock()
	return dm.level
}

// RecordRequest 记录请求
func (dm *DegradationManager) RecordRequest(success bool, latency time.Duration) {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	dm.metrics.TotalRequests++
	if !success {
		dm.metrics.FailedRequests++
	}

	// 更新错误率
	if dm.metrics.TotalRequests > 0 {
		dm.metrics.ErrorRate = float64(dm.metrics.FailedRequests) / float64(dm.metrics.TotalRequests)
	}

	// 更新平均延迟
	dm.metrics.AvgLatency = (dm.metrics.AvgLatency*time.Duration(dm.metrics.TotalRequests-1) + latency) / time.Duration(dm.metrics.TotalRequests)

	// 自动降级检查
	if dm.config.AutoDegrade {
		dm.checkAndDegrade()
	}
}

// checkAndDegrade 检查并自动降级
func (dm *DegradationManager) checkAndDegrade() {
	// 检查错误率
	if dm.metrics.ErrorRate > dm.config.ErrorRateThreshold {
		if dm.level == LevelNormal {
			dm.level = LevelPartial
		} else if dm.level == LevelPartial && dm.metrics.ErrorRate > dm.config.ErrorRateThreshold*1.5 {
			dm.level = LevelFull
		}
		return
	}

	// 检查延迟
	if dm.metrics.AvgLatency > dm.config.LatencyThreshold {
		if dm.level == LevelNormal {
			dm.level = LevelPartial
		}
		return
	}

	// 检查恢复条件
	if dm.level != LevelNormal && dm.metrics.ErrorRate < dm.config.RecoveryThreshold {
		dm.level = LevelNormal
		dm.degradedFeatures = make(map[string]bool)
	}
}

// GetMetrics 获取指标
func (dm *DegradationManager) GetMetrics() DegradationMetrics {
	dm.mu.RLock()
	defer dm.mu.RUnlock()
	return dm.metrics
}

// Reset 重置指标
func (dm *DegradationManager) Reset() {
	dm.mu.Lock()
	defer dm.mu.Unlock()

	dm.metrics = DegradationMetrics{}
	dm.level = LevelNormal
	dm.degradedFeatures = make(map[string]bool)
}

// FallbackHandler 降级处理器
type FallbackHandler struct {
	degradationManager *DegradationManager
	fallbackFn         func(ctx context.Context) (interface{}, error)
}

// NewFallbackHandler 创建降级处理器
func NewFallbackHandler(dm *DegradationManager, fallbackFn func(ctx context.Context) (interface{}, error)) *FallbackHandler {
	return &FallbackHandler{
		degradationManager: dm,
		fallbackFn:         fallbackFn,
	}
}

// Execute 执行（带降级）
func (fh *FallbackHandler) Execute(ctx context.Context, feature string, primaryFn func(ctx context.Context) (interface{}, error)) (interface{}, error) {
	// 检查是否需要降级
	if fh.degradationManager.ShouldDegrade(feature) {
		// 使用降级方案
		if fh.fallbackFn != nil {
			return fh.fallbackFn(ctx)
		}
		// 没有降级方案，返回错误
		return nil, ErrDegraded
	}

	// 执行主要逻辑
	start := time.Now()
	result, err := primaryFn(ctx)
	latency := time.Since(start)

	// 记录请求
	fh.degradationManager.RecordRequest(err == nil, latency)

	return result, err
}

var (
	// ErrDegraded 服务降级错误
	ErrDegraded = errors.New("service degraded")
)
