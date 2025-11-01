package server

import (
	"context"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

// HealthChecker 健康检查器
type HealthChecker struct {
	db     *gorm.DB
	redis  *redis.Client
	logger *log.Helper
}

// HealthResponse 健康检查响应
type HealthResponse struct {
	Status       string                       `json:"status"` // healthy, degraded, unhealthy
	Timestamp    int64                        `json:"timestamp"`
	Version      string                       `json:"version,omitempty"`
	Dependencies map[string]DependencyStatus  `json:"dependencies"`
}

// DependencyStatus 依赖服务状态
type DependencyStatus struct {
	Status    string `json:"status"` // up, down
	Latency   int64  `json:"latency_ms,omitempty"`
	Error     string `json:"error,omitempty"`
	Details   string `json:"details,omitempty"`
}

// NewHealthChecker 创建健康检查器
func NewHealthChecker(db *gorm.DB, redis *redis.Client, logger log.Logger) *HealthChecker {
	return &HealthChecker{
		db:     db,
		redis:  redis,
		logger: log.NewHelper(log.With(logger, "module", "health")),
	}
}

// HealthHandler 健康检查处理器（简单版，用于 K8s liveness）
func (hc *HealthChecker) HealthHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":    "healthy",
			"timestamp": time.Now().Unix(),
		})
	}
}

// ReadinessHandler 就绪检查处理器（用于 K8s readiness）
func (hc *HealthChecker) ReadinessHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
		defer cancel()

		response := HealthResponse{
			Status:       "healthy",
			Timestamp:    time.Now().Unix(),
			Version:      "v2.0.0",
			Dependencies: make(map[string]DependencyStatus),
		}

		// 检查数据库
		dbStatus := hc.checkDatabase(ctx)
		response.Dependencies["database"] = dbStatus
		if dbStatus.Status == "down" {
			response.Status = "unhealthy"
		}

		// 检查 Redis
		redisStatus := hc.checkRedis(ctx)
		response.Dependencies["redis"] = redisStatus
		if redisStatus.Status == "down" {
			response.Status = "unhealthy"
		}

		// 根据状态返回不同的 HTTP 状态码
		statusCode := 200
		if response.Status == "unhealthy" {
			statusCode = 503
		} else if response.Status == "degraded" {
			statusCode = 200 // 降级但仍可用
		}

		c.JSON(statusCode, response)
	}
}

// DetailedHealthHandler 详细健康检查处理器（用于监控）
func (hc *HealthChecker) DetailedHealthHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Second)
		defer cancel()

		response := HealthResponse{
			Status:       "healthy",
			Timestamp:    time.Now().Unix(),
			Version:      "v2.0.0",
			Dependencies: make(map[string]DependencyStatus),
		}

		// 并发检查所有依赖
		type checkResult struct {
			name   string
			status DependencyStatus
		}

		results := make(chan checkResult, 3)

		// 检查数据库
		go func() {
			results <- checkResult{
				name:   "database",
				status: hc.checkDatabase(ctx),
			}
		}()

		// 检查 Redis
		go func() {
			results <- checkResult{
				name:   "redis",
				status: hc.checkRedis(ctx),
			}
		}()

		// 检查数据库连接池
		go func() {
			results <- checkResult{
				name:   "database_pool",
				status: hc.checkDatabasePool(ctx),
			}
		}()

		// 收集结果
		for i := 0; i < 3; i++ {
			result := <-results
			response.Dependencies[result.name] = result.status

			if result.status.Status == "down" {
				response.Status = "unhealthy"
			}
		}

		// 根据状态返回不同的 HTTP 状态码
		statusCode := 200
		if response.Status == "unhealthy" {
			statusCode = 503
		} else if response.Status == "degraded" {
			statusCode = 200
		}

		c.JSON(statusCode, response)
	}
}

// checkDatabase 检查数据库连接
func (hc *HealthChecker) checkDatabase(ctx context.Context) DependencyStatus {
	start := time.Now()

	sqlDB, err := hc.db.DB()
	if err != nil {
		return DependencyStatus{
			Status:  "down",
			Error:   err.Error(),
			Latency: time.Since(start).Milliseconds(),
		}
	}

	err = sqlDB.PingContext(ctx)
	latency := time.Since(start).Milliseconds()

	if err != nil {
		return DependencyStatus{
			Status:  "down",
			Error:   err.Error(),
			Latency: latency,
		}
	}

	return DependencyStatus{
		Status:  "up",
		Latency: latency,
	}
}

// checkRedis 检查 Redis 连接
func (hc *HealthChecker) checkRedis(ctx context.Context) DependencyStatus {
	start := time.Now()

	err := hc.redis.Ping(ctx).Err()
	latency := time.Since(start).Milliseconds()

	if err != nil {
		return DependencyStatus{
			Status:  "down",
			Error:   err.Error(),
			Latency: latency,
		}
	}

	// 检查 Redis 内存使用
	info, err := hc.redis.Info(ctx, "memory").Result()
	details := ""
	if err == nil {
		details = extractRedisMemoryInfo(info)
	}

	return DependencyStatus{
		Status:  "up",
		Latency: latency,
		Details: details,
	}
}

// checkDatabasePool 检查数据库连接池状态
func (hc *HealthChecker) checkDatabasePool(ctx context.Context) DependencyStatus {
	sqlDB, err := hc.db.DB()
	if err != nil {
		return DependencyStatus{
			Status: "down",
			Error:  err.Error(),
		}
	}

	stats := sqlDB.Stats()

	// 检查连接池健康度
	status := "up"
	if stats.OpenConnections >= stats.MaxOpenConnections {
		status = "degraded"
	}

	details := fmt.Sprintf(
		"Open: %d/%d, InUse: %d, Idle: %d, Wait: %d",
		stats.OpenConnections,
		stats.MaxOpenConnections,
		stats.InUse,
		stats.Idle,
		stats.WaitCount,
	)

	return DependencyStatus{
		Status:  status,
		Details: details,
	}
}

// extractRedisMemoryInfo 提取 Redis 内存信息
func extractRedisMemoryInfo(info string) string {
	// 简化实现：提取关键内存指标
	lines := strings.Split(info, "\r\n")
	var usedMemory, maxMemory string

	for _, line := range lines {
		if strings.HasPrefix(line, "used_memory_human:") {
			usedMemory = strings.TrimPrefix(line, "used_memory_human:")
		}
		if strings.HasPrefix(line, "maxmemory_human:") {
			maxMemory = strings.TrimPrefix(line, "maxmemory_human:")
		}
	}

	if usedMemory != "" {
		if maxMemory != "" {
			return fmt.Sprintf("Used: %s / Max: %s", usedMemory, maxMemory)
		}
		return fmt.Sprintf("Used: %s", usedMemory)
	}

	return ""
}

// LivenessProbe K8s liveness 探针
func LivenessProbe() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(200, gin.H{"alive": true})
	}
}

// ReadinessProbe K8s readiness 探针
func ReadinessProbe(hc *HealthChecker) gin.HandlerFunc {
	return hc.ReadinessHandler()
}

// StartupProbe K8s startup 探针（用于慢启动应用）
func StartupProbe() gin.HandlerFunc {
	startTime := time.Now()
	minStartupTime := 5 * time.Second

	return func(c *gin.Context) {
		// 确保应用至少启动了指定时间
		if time.Since(startTime) < minStartupTime {
			c.JSON(503, gin.H{
				"ready":   false,
				"message": "Service is starting up",
			})
			return
		}

		c.JSON(200, gin.H{
			"ready":      true,
			"startup_at": startTime.Unix(),
		})
	}
}
