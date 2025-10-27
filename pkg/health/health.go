package health

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Status 健康状态
type Status string

const (
	// StatusHealthy 健康
	StatusHealthy Status = "healthy"
	// StatusUnhealthy 不健康
	StatusUnhealthy Status = "unhealthy"
	// StatusDegraded 降级
	StatusDegraded Status = "degraded"
)

// CheckResult 检查结果
type CheckResult struct {
	Status    Status                 `json:"status"`
	Timestamp time.Time              `json:"timestamp"`
	Duration  time.Duration          `json:"duration"`
	Details   map[string]interface{} `json:"details,omitempty"`
	Error     string                 `json:"error,omitempty"`
}

// Checker 健康检查器接口
type Checker interface {
	// Check 执行健康检查
	Check(ctx context.Context) CheckResult
	// Name 检查器名称
	Name() string
}

// HealthChecker 健康检查管理器
type HealthChecker struct {
	mu       sync.RWMutex
	checkers map[string]Checker
	results  map[string]CheckResult
}

// NewHealthChecker 创建健康检查管理器
func NewHealthChecker() *HealthChecker {
	return &HealthChecker{
		checkers: make(map[string]Checker),
		results:  make(map[string]CheckResult),
	}
}

// Register 注册检查器
func (h *HealthChecker) Register(checker Checker) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.checkers[checker.Name()] = checker
}

// Check 执行所有检查
func (h *HealthChecker) Check(ctx context.Context) map[string]CheckResult {
	h.mu.RLock()
	checkers := make([]Checker, 0, len(h.checkers))
	for _, checker := range h.checkers {
		checkers = append(checkers, checker)
	}
	h.mu.RUnlock()

	results := make(map[string]CheckResult)
	var wg sync.WaitGroup

	for _, checker := range checkers {
		wg.Add(1)
		go func(c Checker) {
			defer wg.Done()
			result := c.Check(ctx)
			h.mu.Lock()
			h.results[c.Name()] = result
			results[c.Name()] = result
			h.mu.Unlock()
		}(checker)
	}

	wg.Wait()
	return results
}

// GetStatus 获取整体状态
func (h *HealthChecker) GetStatus(ctx context.Context) Status {
	results := h.Check(ctx)

	hasUnhealthy := false
	hasDegraded := false

	for _, result := range results {
		switch result.Status {
		case StatusUnhealthy:
			hasUnhealthy = true
		case StatusDegraded:
			hasDegraded = true
		}
	}

	if hasUnhealthy {
		return StatusUnhealthy
	}
	if hasDegraded {
		return StatusDegraded
	}
	return StatusHealthy
}

// DatabaseChecker 数据库健康检查
type DatabaseChecker struct {
	name   string
	pingFn func(context.Context) error
}

// NewDatabaseChecker 创建数据库检查器
func NewDatabaseChecker(name string, pingFn func(context.Context) error) *DatabaseChecker {
	return &DatabaseChecker{
		name:   name,
		pingFn: pingFn,
	}
}

// Name 返回检查器名称
func (d *DatabaseChecker) Name() string {
	return d.name
}

// Check 执行检查
func (d *DatabaseChecker) Check(ctx context.Context) CheckResult {
	start := time.Now()
	err := d.pingFn(ctx)
	duration := time.Since(start)

	if err != nil {
		return CheckResult{
			Status:    StatusUnhealthy,
			Timestamp: time.Now(),
			Duration:  duration,
			Error:     err.Error(),
		}
	}

	return CheckResult{
		Status:    StatusHealthy,
		Timestamp: time.Now(),
		Duration:  duration,
	}
}

// RedisChecker Redis健康检查
type RedisChecker struct {
	name   string
	pingFn func(context.Context) error
}

// NewRedisChecker 创建Redis检查器
func NewRedisChecker(name string, pingFn func(context.Context) error) *RedisChecker {
	return &RedisChecker{
		name:   name,
		pingFn: pingFn,
	}
}

// Name 返回检查器名称
func (r *RedisChecker) Name() string {
	return r.name
}

// Check 执行检查
func (r *RedisChecker) Check(ctx context.Context) CheckResult {
	start := time.Now()
	err := r.pingFn(ctx)
	duration := time.Since(start)

	if err != nil {
		return CheckResult{
			Status:    StatusUnhealthy,
			Timestamp: time.Now(),
			Duration:  duration,
			Error:     err.Error(),
		}
	}

	return CheckResult{
		Status:    StatusHealthy,
		Timestamp: time.Now(),
		Duration:  duration,
	}
}

// ServiceChecker 外部服务健康检查
type ServiceChecker struct {
	name      string
	checkFn   func(context.Context) error
	threshold time.Duration // 响应时间阈值
}

// NewServiceChecker 创建服务检查器
func NewServiceChecker(name string, checkFn func(context.Context) error, threshold time.Duration) *ServiceChecker {
	return &ServiceChecker{
		name:      name,
		checkFn:   checkFn,
		threshold: threshold,
	}
}

// Name 返回检查器名称
func (s *ServiceChecker) Name() string {
	return s.name
}

// Check 执行检查
func (s *ServiceChecker) Check(ctx context.Context) CheckResult {
	start := time.Now()
	err := s.checkFn(ctx)
	duration := time.Since(start)

	if err != nil {
		return CheckResult{
			Status:    StatusUnhealthy,
			Timestamp: time.Now(),
			Duration:  duration,
			Error:     err.Error(),
		}
	}

	// 检查响应时间
	if s.threshold > 0 && duration > s.threshold {
		return CheckResult{
			Status:    StatusDegraded,
			Timestamp: time.Now(),
			Duration:  duration,
			Details: map[string]interface{}{
				"threshold": s.threshold.String(),
				"actual":    duration.String(),
			},
			Error: fmt.Sprintf("response time exceeds threshold: %v > %v", duration, s.threshold),
		}
	}

	return CheckResult{
		Status:    StatusHealthy,
		Timestamp: time.Now(),
		Duration:  duration,
	}
}

// ReadinessChecker 就绪检查（用于K8s）
type ReadinessChecker struct {
	*HealthChecker
	dependencies []string // 必须健康的依赖
}

// NewReadinessChecker 创建就绪检查器
func NewReadinessChecker(healthChecker *HealthChecker, dependencies []string) *ReadinessChecker {
	return &ReadinessChecker{
		HealthChecker: healthChecker,
		dependencies:  dependencies,
	}
}

// IsReady 检查是否就绪
func (r *ReadinessChecker) IsReady(ctx context.Context) bool {
	results := r.Check(ctx)

	for _, dep := range r.dependencies {
		result, ok := results[dep]
		if !ok || result.Status != StatusHealthy {
			return false
		}
	}

	return true
}
