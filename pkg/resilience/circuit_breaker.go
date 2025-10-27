package resilience

import (
	"context"
	"errors"
	"sync"
	"time"
)

var (
	// ErrCircuitOpen 熔断器打开错误
	ErrCircuitOpen = errors.New("circuit breaker is open")
	// ErrTooManyRequests 请求过多错误
	ErrTooManyRequests = errors.New("too many requests")
)

// State 熔断器状态
type State int

const (
	// StateClosed 关闭状态 - 正常运行
	StateClosed State = iota
	// StateOpen 打开状态 - 熔断中
	StateOpen
	// StateHalfOpen 半开状态 - 尝试恢复
	StateHalfOpen
)

// String 返回状态字符串
func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}

// CircuitBreaker 熔断器
type CircuitBreaker struct {
	mu            sync.RWMutex
	state         State
	failureCount  int64
	successCount  int64
	lastFailTime  time.Time
	lastStateTime time.Time
	config        Config
}

// Config 熔断器配置
type Config struct {
	// MaxFailures 最大失败次数（触发熔断）
	MaxFailures int64
	// Timeout 熔断器打开后的超时时间
	Timeout time.Duration
	// MaxRequests 半开状态允许的最大请求数
	MaxRequests int64
	// SuccessThreshold 半开状态需要的成功次数（恢复关闭）
	SuccessThreshold int64
	// OnStateChange 状态变化回调
	OnStateChange func(from, to State)
}

// DefaultConfig 默认配置
func DefaultConfig() Config {
	return Config{
		MaxFailures:      5,
		Timeout:          60 * time.Second,
		MaxRequests:      3,
		SuccessThreshold: 2,
	}
}

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(config Config) *CircuitBreaker {
	if config.MaxFailures <= 0 {
		config.MaxFailures = DefaultConfig().MaxFailures
	}
	if config.Timeout <= 0 {
		config.Timeout = DefaultConfig().Timeout
	}
	if config.MaxRequests <= 0 {
		config.MaxRequests = DefaultConfig().MaxRequests
	}
	if config.SuccessThreshold <= 0 {
		config.SuccessThreshold = DefaultConfig().SuccessThreshold
	}

	return &CircuitBreaker{
		state:         StateClosed,
		lastStateTime: time.Now(),
		config:        config,
	}
}

// Execute 执行函数，带熔断保护
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
	// 检查是否可以执行
	if err := cb.beforeRequest(); err != nil {
		return err
	}

	// 执行函数
	err := fn()

	// 记录结果
	cb.afterRequest(err)

	return err
}

// beforeRequest 请求前检查
func (cb *CircuitBreaker) beforeRequest() error {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	switch cb.state {
	case StateClosed:
		// 关闭状态，允许请求
		return nil

	case StateOpen:
		// 检查是否可以转为半开状态
		if now.Sub(cb.lastStateTime) > cb.config.Timeout {
			cb.setState(StateHalfOpen, now)
			return nil
		}
		return ErrCircuitOpen

	case StateHalfOpen:
		// 半开状态，限制请求数
		if cb.successCount+cb.failureCount >= cb.config.MaxRequests {
			return ErrTooManyRequests
		}
		return nil

	default:
		return ErrCircuitOpen
	}
}

// afterRequest 请求后处理
func (cb *CircuitBreaker) afterRequest(err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	if err != nil {
		// 失败
		cb.onFailure(now)
	} else {
		// 成功
		cb.onSuccess(now)
	}
}

// onFailure 处理失败
func (cb *CircuitBreaker) onFailure(now time.Time) {
	cb.failureCount++
	cb.lastFailTime = now

	switch cb.state {
	case StateClosed:
		// 检查是否达到失败阈值
		if cb.failureCount >= cb.config.MaxFailures {
			cb.setState(StateOpen, now)
		}

	case StateHalfOpen:
		// 半开状态失败，重新打开
		cb.setState(StateOpen, now)
	}
}

// onSuccess 处理成功
func (cb *CircuitBreaker) onSuccess(now time.Time) {
	switch cb.state {
	case StateClosed:
		// 关闭状态，重置失败计数
		cb.failureCount = 0

	case StateHalfOpen:
		// 半开状态，增加成功计数
		cb.successCount++
		if cb.successCount >= cb.config.SuccessThreshold {
			// 达到成功阈值，关闭熔断器
			cb.setState(StateClosed, now)
		}
	}
}

// setState 设置状态
func (cb *CircuitBreaker) setState(newState State, now time.Time) {
	oldState := cb.state

	if oldState == newState {
		return
	}

	cb.state = newState
	cb.lastStateTime = now

	// 状态转换时重置计数器
	switch newState {
	case StateClosed:
		cb.failureCount = 0
		cb.successCount = 0
	case StateOpen:
		cb.successCount = 0
	case StateHalfOpen:
		cb.failureCount = 0
		cb.successCount = 0
	}

	// 回调
	if cb.config.OnStateChange != nil {
		cb.config.OnStateChange(oldState, newState)
	}
}

// State 获取当前状态
func (cb *CircuitBreaker) State() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// Metrics 获取指标
func (cb *CircuitBreaker) Metrics() Metrics {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	return Metrics{
		State:         cb.state,
		FailureCount:  cb.failureCount,
		SuccessCount:  cb.successCount,
		LastFailTime:  cb.lastFailTime,
		LastStateTime: cb.lastStateTime,
	}
}

// Metrics 熔断器指标
type Metrics struct {
	State         State
	FailureCount  int64
	SuccessCount  int64
	LastFailTime  time.Time
	LastStateTime time.Time
}

// Reset 重置熔断器
func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.state = StateClosed
	cb.failureCount = 0
	cb.successCount = 0
	cb.lastStateTime = time.Now()
}
