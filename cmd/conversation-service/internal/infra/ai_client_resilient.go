package infra

import (
	"context"
	"fmt"
	"math"
	"math/rand"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/sony/gobreaker"
)

// ResilientAIClient 具有弹性的 AI 客户端（带熔断和重试）
type ResilientAIClient struct {
	baseClient    *AIClient
	circuitBreaker *gobreaker.CircuitBreaker
	retryConfig   *RetryConfig
	logger        *log.Helper
}

// RetryConfig 重试配置
type RetryConfig struct {
	MaxAttempts     int           // 最大重试次数
	InitialInterval time.Duration // 初始退避时间
	MaxInterval     time.Duration // 最大退避时间
	Multiplier      float64       // 退避时间倍数
	RandomFactor    float64       // 随机因子（jitter）
}

// CircuitBreakerConfig 熔断器配置
type CircuitBreakerConfig struct {
	Name              string        // 熔断器名称
	MaxRequests       uint32        // 半开状态允许的最大请求数
	Interval          time.Duration // 统计窗口
	Timeout           time.Duration // 熔断后恢复时间
	FailureThreshold  float64       // 失败率阈值（0.0-1.0）
	MinRequests       uint32        // 最小请求数（达到后才计算失败率）
}

// NewResilientAIClient 创建具有弹性的 AI 客户端
func NewResilientAIClient(
	baseClient *AIClient,
	cbConfig *CircuitBreakerConfig,
	retryConfig *RetryConfig,
	logger log.Logger,
) *ResilientAIClient {
	// 默认熔断器配置
	if cbConfig == nil {
		cbConfig = &CircuitBreakerConfig{
			Name:             "ai-orchestrator",
			MaxRequests:      3,
			Interval:         10 * time.Second,
			Timeout:          30 * time.Second,
			FailureThreshold: 0.5,
			MinRequests:      3,
		}
	}

	// 默认重试配置
	if retryConfig == nil {
		retryConfig = &RetryConfig{
			MaxAttempts:     3,
			InitialInterval: 100 * time.Millisecond,
			MaxInterval:     10 * time.Second,
			Multiplier:      2.0,
			RandomFactor:    0.1,
		}
	}

	logHelper := log.NewHelper(log.With(logger, "module", "resilient-ai-client"))

	// 创建熔断器
	cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
		Name:        cbConfig.Name,
		MaxRequests: cbConfig.MaxRequests,
		Interval:    cbConfig.Interval,
		Timeout:     cbConfig.Timeout,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// 检查是否达到最小请求数
			if counts.Requests < cbConfig.MinRequests {
				return false
			}

			// 计算失败率
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			shouldTrip := failureRatio >= cbConfig.FailureThreshold

			if shouldTrip {
				logHelper.Warnf("Circuit breaker tripping: requests=%d, failures=%d, ratio=%.2f",
					counts.Requests, counts.TotalFailures, failureRatio)
			}

			return shouldTrip
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			logHelper.Infof("Circuit breaker state change: %s -> %s", from, to)
		},
	})

	return &ResilientAIClient{
		baseClient:     baseClient,
		circuitBreaker: cb,
		retryConfig:    retryConfig,
		logger:         logHelper,
	}
}

// ProcessMessage 处理消息（带熔断和重试）
func (c *ResilientAIClient) ProcessMessage(ctx context.Context, req *ProcessRequest) (*ProcessResponse, error) {
	return c.executeWithRetry(ctx, func() (*ProcessResponse, error) {
		// 通过熔断器执行
		result, err := c.circuitBreaker.Execute(func() (interface{}, error) {
			return c.baseClient.ProcessMessage(ctx, req)
		})

		if err != nil {
			// 检查是否熔断
			if err == gobreaker.ErrOpenState {
				c.logger.Warn("Circuit breaker is open, returning fallback response")
				return c.getFallbackResponse(req), nil
			}
			return nil, err
		}

		return result.(*ProcessResponse), nil
	})
}

// ProcessMessageStream 处理流式消息（带熔断和重试）
func (c *ResilientAIClient) ProcessMessageStream(
	ctx context.Context,
	req *ProcessRequest,
) (<-chan *StreamChunk, <-chan error) {
	chunkChan := make(chan *StreamChunk, 100)
	errChan := make(chan error, 1)

	go func() {
		defer close(chunkChan)
		defer close(errChan)

		// 流式请求不重试（已经开始流式传输）
		// 但仍然通过熔断器
		err := c.executeStream(ctx, req, chunkChan)
		if err != nil {
			// 检查是否熔断
			if err == gobreaker.ErrOpenState {
				c.logger.Warn("Circuit breaker is open for stream request")
				// 发送降级消息
				fallbackChunk := &StreamChunk{
					EventType: "error",
					Delta:     "AI 服务暂时不可用，请稍后重试。",
					Finished:  true,
				}
				chunkChan <- fallbackChunk
				return
			}
			errChan <- err
		}
	}()

	return chunkChan, errChan
}

// executeStream 执行流式请求
func (c *ResilientAIClient) executeStream(
	ctx context.Context,
	req *ProcessRequest,
	outputChan chan<- *StreamChunk,
) error {
	_, err := c.circuitBreaker.Execute(func() (interface{}, error) {
		// 获取流式通道
		chunkChan, errChan := c.baseClient.ProcessMessageStream(ctx, req)

		// 转发流式数据
		for {
			select {
			case chunk, ok := <-chunkChan:
				if !ok {
					return nil, nil
				}
				outputChan <- chunk
				if chunk.Finished {
					return nil, nil
				}

			case err := <-errChan:
				if err != nil {
					return nil, err
				}

			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}
	})

	return err
}

// executeWithRetry 执行带重试的操作
func (c *ResilientAIClient) executeWithRetry(
	ctx context.Context,
	operation func() (*ProcessResponse, error),
) (*ProcessResponse, error) {
	var lastErr error

	for attempt := 0; attempt < c.retryConfig.MaxAttempts; attempt++ {
		// 执行操作
		resp, err := operation()

		if err == nil {
			// 成功
			if attempt > 0 {
				c.logger.Infof("Request succeeded after %d retries", attempt)
			}
			return resp, nil
		}

		lastErr = err

		// 检查是否熔断（熔断不重试）
		if err == gobreaker.ErrOpenState {
			c.logger.Warn("Circuit breaker is open, not retrying")
			return resp, nil // 返回降级响应
		}

		// 检查是否可重试
		if !c.isRetryable(err) {
			c.logger.Warnf("Error is not retryable: %v", err)
			return nil, err
		}

		// 最后一次尝试，不等待
		if attempt == c.retryConfig.MaxAttempts-1 {
			break
		}

		// 计算退避时间
		backoff := c.calculateBackoff(attempt)

		c.logger.Infof("Request failed (attempt %d/%d), retrying after %v: %v",
			attempt+1, c.retryConfig.MaxAttempts, backoff, err)

		// 等待退避时间
		select {
		case <-time.After(backoff):
			// 继续重试
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}

	c.logger.Errorf("Request failed after %d attempts: %v", c.retryConfig.MaxAttempts, lastErr)
	return nil, fmt.Errorf("request failed after %d attempts: %w", c.retryConfig.MaxAttempts, lastErr)
}

// calculateBackoff 计算退避时间（指数退避 + jitter）
func (c *ResilientAIClient) calculateBackoff(attempt int) time.Duration {
	// 指数退避
	interval := float64(c.retryConfig.InitialInterval) * math.Pow(c.retryConfig.Multiplier, float64(attempt))

	// 限制最大值
	if interval > float64(c.retryConfig.MaxInterval) {
		interval = float64(c.retryConfig.MaxInterval)
	}

	// 添加随机 jitter（防止惊群效应）
	jitter := interval * c.retryConfig.RandomFactor
	interval = interval + (rand.Float64()*2-1)*jitter

	return time.Duration(interval)
}

// isRetryable 判断错误是否可重试
func (c *ResilientAIClient) isRetryable(err error) bool {
	// 可重试的错误类型
	retryableErrors := []string{
		"timeout",
		"temporary",
		"connection refused",
		"EOF",
		"broken pipe",
	}

	errStr := err.Error()
	for _, retryable := range retryableErrors {
		if contains(errStr, retryable) {
			return true
		}
	}

	return false
}

// getFallbackResponse 获取降级响应
func (c *ResilientAIClient) getFallbackResponse(req *ProcessRequest) *ProcessResponse {
	return &ProcessResponse{
		TaskID: "fallback",
		Reply:  "抱歉，AI 服务暂时不可用，请稍后重试。我们正在努力恢复服务。",
		Engine: "fallback",
		Metadata: map[string]string{
			"fallback": "true",
			"reason":   "circuit_breaker_open",
		},
	}
}

// GetCircuitBreakerState 获取熔断器状态
func (c *ResilientAIClient) GetCircuitBreakerState() gobreaker.State {
	return c.circuitBreaker.State()
}

// GetCircuitBreakerCounts 获取熔断器统计
func (c *ResilientAIClient) GetCircuitBreakerCounts() gobreaker.Counts {
	return c.circuitBreaker.Counts()
}

// ResetCircuitBreaker 重置熔断器（紧急情况）
func (c *ResilientAIClient) ResetCircuitBreaker() {
	// gobreaker 不支持直接重置，需要等待 Timeout
	c.logger.Warn("Circuit breaker reset requested (will auto-recover after timeout)")
}

// contains 辅助函数：检查字符串包含
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && (s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || containsMiddle(s, substr)))
}

func containsMiddle(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// Close 关闭客户端
func (c *ResilientAIClient) Close() error {
	return c.baseClient.Close()
}
