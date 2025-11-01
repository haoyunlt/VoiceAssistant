package health

import (
	"context"
	"encoding/json"
	"time"
)

// HealthStatus 健康状态枚举
type HealthStatus string

const (
	StatusHealthy   HealthStatus = "healthy"   // 健康
	StatusDegraded  HealthStatus = "degraded"  // 降级（部分功能不可用）
	StatusUnhealthy HealthStatus = "unhealthy" // 不健康
)

// UnifiedHealthResponse 统一健康检查响应
type UnifiedHealthResponse struct {
	// 基础字段
	Status    HealthStatus `json:"status"`              // 健康状态
	Service   string       `json:"service"`             // 服务名称
	Version   string       `json:"version"`             // 服务版本
	Timestamp string       `json:"timestamp"`           // 时间戳
	Uptime    int64        `json:"uptime"`              // 运行时间（秒）
	
	// 依赖检查
	Dependencies map[string]DependencyHealth `json:"dependencies,omitempty"` // 依赖服务健康状态
	
	// 系统信息
	System *SystemInfo `json:"system,omitempty"` // 系统信息
	
	// 可选字段
	Message string `json:"message,omitempty"` // 附加消息
}

// DependencyHealth 依赖服务健康状态
type DependencyHealth struct {
	Status    HealthStatus `json:"status"`              // 健康状态
	Latency   int64        `json:"latency,omitempty"`   // 响应延迟（毫秒）
	Message   string       `json:"message,omitempty"`   // 状态消息
	LastCheck string       `json:"last_check,omitempty"` // 最后检查时间
}

// SystemInfo 系统信息
type SystemInfo struct {
	GoVersion     string  `json:"go_version,omitempty"`     // Go版本
	PythonVersion string  `json:"python_version,omitempty"` // Python版本
	OS            string  `json:"os,omitempty"`             // 操作系统
	Arch          string  `json:"arch,omitempty"`           // 架构
	CPUUsage      float64 `json:"cpu_usage,omitempty"`      // CPU使用率（%）
	MemoryUsage   float64 `json:"memory_usage,omitempty"`   // 内存使用率（%）
	Goroutines    int     `json:"goroutines,omitempty"`     // Goroutine数量
}

// ReadinessResponse 就绪检查响应
type ReadinessResponse struct {
	Ready        bool                        `json:"ready"`                  // 是否就绪
	Service      string                      `json:"service"`                // 服务名称
	Timestamp    string                      `json:"timestamp"`              // 时间戳
	Checks       map[string]bool             `json:"checks"`                 // 各项检查结果
	Dependencies map[string]DependencyHealth `json:"dependencies,omitempty"` // 依赖状态
	Message      string                      `json:"message,omitempty"`      // 附加消息
}

// HealthChecker 健康检查器接口
type HealthChecker interface {
	// Check 执行健康检查
	Check(ctx context.Context) *UnifiedHealthResponse
	
	// CheckDependency 检查依赖服务
	CheckDependency(ctx context.Context, name string) *DependencyHealth
	
	// IsReady 检查是否就绪
	IsReady(ctx context.Context) *ReadinessResponse
}

// NewHealthResponse 创建健康响应
func NewHealthResponse(service, version string, startTime time.Time) *UnifiedHealthResponse {
	uptime := time.Since(startTime).Seconds()
	
	return &UnifiedHealthResponse{
		Status:    StatusHealthy,
		Service:   service,
		Version:   version,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Uptime:    int64(uptime),
	}
}

// WithDependencies 添加依赖检查
func (h *UnifiedHealthResponse) WithDependencies(deps map[string]DependencyHealth) *UnifiedHealthResponse {
	h.Dependencies = deps
	
	// 根据依赖状态更新整体状态
	hasUnhealthy := false
	hasDegraded := false
	
	for _, dep := range deps {
		if dep.Status == StatusUnhealthy {
			hasUnhealthy = true
		} else if dep.Status == StatusDegraded {
			hasDegraded = true
		}
	}
	
	if hasUnhealthy {
		h.Status = StatusUnhealthy
	} else if hasDegraded {
		h.Status = StatusDegraded
	}
	
	return h
}

// WithSystem 添加系统信息
func (h *UnifiedHealthResponse) WithSystem(sys *SystemInfo) *UnifiedHealthResponse {
	h.System = sys
	return h
}

// WithMessage 添加消息
func (h *UnifiedHealthResponse) WithMessage(message string) *UnifiedHealthResponse {
	h.Message = message
	return h
}

// ToJSON 转换为JSON
func (h *UnifiedHealthResponse) ToJSON() ([]byte, error) {
	return json.Marshal(h)
}

// NewReadinessResponse 创建就绪响应
func NewReadinessResponse(service string) *ReadinessResponse {
	return &ReadinessResponse{
		Ready:     true,
		Service:   service,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Checks:    make(map[string]bool),
	}
}

// AddCheck 添加检查项
func (r *ReadinessResponse) AddCheck(name string, passed bool) *ReadinessResponse {
	r.Checks[name] = passed
	
	// 只要有一项失败，整体就不就绪
	if !passed {
		r.Ready = false
	}
	
	return r
}

// WithDependencies 添加依赖状态
func (r *ReadinessResponse) WithDependencies(deps map[string]DependencyHealth) *ReadinessResponse {
	r.Dependencies = deps
	
	// 检查依赖是否都健康
	for _, dep := range deps {
		if dep.Status == StatusUnhealthy {
			r.Ready = false
			break
		}
	}
	
	return r
}

// WithMessage 添加消息
func (r *ReadinessResponse) WithMessage(message string) *ReadinessResponse {
	r.Message = message
	return r
}

// ToJSON 转换为JSON
func (r *ReadinessResponse) ToJSON() ([]byte, error) {
	return json.Marshal(r)
}

// CheckDependencyWithTimeout 带超时的依赖检查
func CheckDependencyWithTimeout(ctx context.Context, name string, checkFn func() error, timeout time.Duration) *DependencyHealth {
	start := time.Now()
	
	// 创建带超时的context
	checkCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	
	// 执行检查
	errCh := make(chan error, 1)
	go func() {
		errCh <- checkFn()
	}()
	
	var err error
	select {
	case err = <-errCh:
		// 检查完成
	case <-checkCtx.Done():
		// 超时
		err = checkCtx.Err()
	}
	
	latency := time.Since(start).Milliseconds()
	
	// 构建响应
	health := &DependencyHealth{
		Latency:   latency,
		LastCheck: time.Now().UTC().Format(time.RFC3339),
	}
	
	if err != nil {
		health.Status = StatusUnhealthy
		health.Message = err.Error()
	} else {
		health.Status = StatusHealthy
		health.Message = "OK"
	}
	
	return health
}

// StandardHealthChecks 标准健康检查项
var StandardHealthChecks = struct {
	Database      string
	Redis         string
	MessageQueue  string
	ExternalAPI   string
	FileStorage   string
	VectorDB      string
	GraphDB       string
	SearchEngine  string
}{
	Database:     "database",
	Redis:        "redis",
	MessageQueue: "message_queue",
	ExternalAPI:  "external_api",
	FileStorage:  "file_storage",
	VectorDB:     "vector_db",
	GraphDB:      "graph_db",
	SearchEngine: "search_engine",
}

