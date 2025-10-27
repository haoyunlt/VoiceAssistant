package infrastructure

import (
	"context"
	"errors"
	"sync"
	"time"
)

// CircuitState 熔断器状态
type CircuitState int

const (
	// StateClosed 关闭状态（正常）
	StateClosed CircuitState = iota
	// StateOpen 开启状态（熔断）
	StateOpen
	// StateHalfOpen 半开状态（尝试恢复）
	StateHalfOpen
)

// String 返回状态字符串
func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half_open"
	default:
		return "unknown"
	}
}

// CircuitBreaker 熔断器
type CircuitBreaker struct {
	maxFailures  int           // 最大失败次数
	timeout      time.Duration // 执行超时时间
	resetTimeout time.Duration // 重置超时时间

	state        CircuitState
	failures     int
	lastFailTime time.Time
	mu           sync.RWMutex
}

// ErrCircuitOpen 熔断器开启错误
var ErrCircuitOpen = errors.New("circuit breaker is open")

// ErrTimeout 执行超时错误
var ErrTimeout = errors.New("execution timeout")

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(maxFailures int, timeout, resetTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		maxFailures:  maxFailures,
		timeout:      timeout,
		resetTimeout: resetTimeout,
		state:        StateClosed,
		failures:     0,
	}
}

// Execute 执行函数（带熔断保护）
func (cb *CircuitBreaker) Execute(fn func() error) error {
	// 检查是否可以执行
	if err := cb.beforeRequest(); err != nil {
		return err
	}

	// 执行函数（带超时）
	done := make(chan error, 1)
	go func() {
		done <- fn()
	}()

	select {
	case err := <-done:
		cb.afterRequest(err)
		return err

	case <-time.After(cb.timeout):
		cb.afterRequest(ErrTimeout)
		return ErrTimeout
	}
}

// ExecuteWithContext 执行函数（带上下文和熔断保护）
func (cb *CircuitBreaker) ExecuteWithContext(ctx context.Context, fn func(context.Context) error) error {
	// 检查是否可以执行
	if err := cb.beforeRequest(); err != nil {
		return err
	}

	// 创建带超时的上下文
	ctx, cancel := context.WithTimeout(ctx, cb.timeout)
	defer cancel()

	// 执行函数
	done := make(chan error, 1)
	go func() {
		done <- fn(ctx)
	}()

	select {
	case err := <-done:
		cb.afterRequest(err)
		return err

	case <-ctx.Done():
		cb.afterRequest(ctx.Err())
		return ctx.Err()
	}
}

// beforeRequest 请求前检查
func (cb *CircuitBreaker) beforeRequest() error {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	// 如果熔断器是开启状态
	if cb.state == StateOpen {
		// 检查是否可以尝试恢复
		if time.Since(cb.lastFailTime) > cb.resetTimeout {
			cb.state = StateHalfOpen
			cb.failures = 0
			return nil
		}
		return ErrCircuitOpen
	}

	return nil
}

// afterRequest 请求后处理
func (cb *CircuitBreaker) afterRequest(err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		// 失败处理
		cb.failures++
		cb.lastFailTime = time.Now()

		if cb.failures >= cb.maxFailures {
			cb.state = StateOpen
		}
	} else {
		// 成功处理
		if cb.state == StateHalfOpen {
			// 半开状态下成功，恢复到关闭状态
			cb.state = StateClosed
		}
		cb.failures = 0
	}
}

// GetState 获取当前状态
func (cb *CircuitBreaker) GetState() CircuitState {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// GetFailures 获取失败次数
func (cb *CircuitBreaker) GetFailures() int {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.failures
}

// Reset 重置熔断器
func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.state = StateClosed
	cb.failures = 0
}

// Stats 获取统计信息
func (cb *CircuitBreaker) Stats() map[string]interface{} {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	return map[string]interface{}{
		"state":           cb.state.String(),
		"failures":        cb.failures,
		"max_failures":    cb.maxFailures,
		"last_fail_time":  cb.lastFailTime,
		"timeout":         cb.timeout.String(),
		"reset_timeout":   cb.resetTimeout.String(),
	}
}
