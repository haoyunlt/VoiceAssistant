package application

import (
	"context"
	"fmt"
	"sync"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"
)

// FallbackRule 降级规则
type FallbackRule struct {
	ModelID        string                `json:"model_id"`        // 模型ID
	Fallbacks      []string              `json:"fallbacks"`       // 降级链 (按顺序尝试)
	MaxRetries     int                   `json:"max_retries"`     // 最大重试次数
	RetryDelay     time.Duration         `json:"retry_delay"`     // 重试延迟
	CircuitBreaker *CircuitBreakerConfig `json:"circuit_breaker"` // 熔断器配置
}

// CircuitBreakerConfig 熔断器配置
type CircuitBreakerConfig struct {
	Enabled          bool          `json:"enabled"`            // 是否启用
	FailureThreshold int           `json:"failure_threshold"`  // 失败阈值
	SuccessThreshold int           `json:"success_threshold"`  // 恢复阈值
	Timeout          time.Duration `json:"timeout"`            // 超时时间
	HalfOpenRequests int           `json:"half_open_requests"` // 半开状态允许的请求数
}

// CircuitState 熔断器状态
type CircuitState string

const (
	StateClosed   CircuitState = "closed"    // 关闭 (正常)
	StateOpen     CircuitState = "open"      // 打开 (熔断)
	StateHalfOpen CircuitState = "half_open" // 半开 (试探)
)

// CircuitBreaker 熔断器
type CircuitBreaker struct {
	config           *CircuitBreakerConfig
	state            CircuitState
	failureCount     int
	successCount     int
	lastFailureTime  time.Time
	halfOpenRequests int
	mu               sync.RWMutex
}

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(config *CircuitBreakerConfig) *CircuitBreaker {
	return &CircuitBreaker{
		config:       config,
		state:        StateClosed,
		failureCount: 0,
		successCount: 0,
	}
}

// Allow 检查是否允许请求
func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if !cb.config.Enabled {
		return true
	}

	switch cb.state {
	case StateClosed:
		// 关闭状态：允许所有请求
		return true

	case StateOpen:
		// 打开状态：检查是否应该转为半开
		if time.Since(cb.lastFailureTime) > cb.config.Timeout {
			cb.state = StateHalfOpen
			cb.halfOpenRequests = 0
			return true
		}
		return false

	case StateHalfOpen:
		// 半开状态：允许有限的请求
		if cb.halfOpenRequests < cb.config.HalfOpenRequests {
			cb.halfOpenRequests++
			return true
		}
		return false

	default:
		return true
	}
}

// RecordSuccess 记录成功
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if !cb.config.Enabled {
		return
	}

	cb.failureCount = 0
	cb.successCount++

	// 半开状态下连续成功，恢复到关闭状态
	if cb.state == StateHalfOpen && cb.successCount >= cb.config.SuccessThreshold {
		cb.state = StateClosed
		cb.successCount = 0
		cb.halfOpenRequests = 0
	}
}

// RecordFailure 记录失败
func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if !cb.config.Enabled {
		return
	}

	cb.successCount = 0
	cb.failureCount++
	cb.lastFailureTime = time.Now()

	// 失败次数达到阈值，打开熔断器
	if cb.failureCount >= cb.config.FailureThreshold {
		cb.state = StateOpen
		cb.halfOpenRequests = 0
	}
}

// GetState 获取状态
func (cb *CircuitBreaker) GetState() CircuitState {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// FallbackManager 降级管理器
type FallbackManager struct {
	registry        *domain.ModelRegistry
	rules           map[string]*FallbackRule   // model_id -> FallbackRule
	circuitBreakers map[string]*CircuitBreaker // model_id -> CircuitBreaker
	mu              sync.RWMutex
}

// NewFallbackManager 创建降级管理器
func NewFallbackManager(registry *domain.ModelRegistry) *FallbackManager {
	manager := &FallbackManager{
		registry:        registry,
		rules:           make(map[string]*FallbackRule),
		circuitBreakers: make(map[string]*CircuitBreaker),
	}

	// 初始化默认规则
	manager.initDefaultRules()

	return manager
}

// initDefaultRules 初始化默认降级规则
func (m *FallbackManager) initDefaultRules() {
	defaultCircuitBreaker := &CircuitBreakerConfig{
		Enabled:          true,
		FailureThreshold: 5,
		SuccessThreshold: 2,
		Timeout:          30 * time.Second,
		HalfOpenRequests: 3,
	}

	// GPT-4 降级到 GPT-3.5
	m.AddRule("openai-gpt-4", &FallbackRule{
		ModelID:        "openai-gpt-4",
		Fallbacks:      []string{"openai-gpt-3.5-turbo-16k", "openai-gpt-3.5-turbo"},
		MaxRetries:     2,
		RetryDelay:     1 * time.Second,
		CircuitBreaker: defaultCircuitBreaker,
	})

	// Claude Opus 降级到 Sonnet
	m.AddRule("claude-3-opus", &FallbackRule{
		ModelID:        "claude-3-opus",
		Fallbacks:      []string{"claude-3-sonnet", "openai-gpt-3.5-turbo"},
		MaxRetries:     2,
		RetryDelay:     1 * time.Second,
		CircuitBreaker: defaultCircuitBreaker,
	})

	// GPT-3.5 降级到智谱
	m.AddRule("openai-gpt-3.5-turbo", &FallbackRule{
		ModelID:        "openai-gpt-3.5-turbo",
		Fallbacks:      []string{"zhipu-glm-4"},
		MaxRetries:     1,
		RetryDelay:     500 * time.Millisecond,
		CircuitBreaker: defaultCircuitBreaker,
	})
}

// AddRule 添加降级规则
func (m *FallbackManager) AddRule(modelID string, rule *FallbackRule) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.rules[modelID] = rule

	// 创建熔断器
	if rule.CircuitBreaker != nil && rule.CircuitBreaker.Enabled {
		m.circuitBreakers[modelID] = NewCircuitBreaker(rule.CircuitBreaker)
	}
}

// GetFallback 获取降级模型
func (m *FallbackManager) GetFallback(ctx context.Context, modelID string, attempt int) (string, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	rule, exists := m.rules[modelID]
	if !exists {
		return "", fmt.Errorf("no fallback rule for model: %s", modelID)
	}

	// 检查降级链长度
	if attempt >= len(rule.Fallbacks) {
		return "", fmt.Errorf("no more fallback options for model: %s", modelID)
	}

	fallbackModelID := rule.Fallbacks[attempt]

	// 检查降级模型是否可用
	fallbackModel, err := m.registry.Get(fallbackModelID)
	if err != nil {
		return "", fmt.Errorf("fallback model not found: %s", fallbackModelID)
	}

	if !fallbackModel.IsHealthy() {
		// 递归尝试下一个降级
		if attempt+1 < len(rule.Fallbacks) {
			return m.GetFallback(ctx, modelID, attempt+1)
		}
		return "", fmt.Errorf("all fallback models are unhealthy")
	}

	return fallbackModelID, nil
}

// ExecuteWithFallback 执行请求（带自动降级）
func (m *FallbackManager) ExecuteWithFallback(
	ctx context.Context,
	modelID string,
	executor func(string) error,
) error {
	// 1. 检查熔断器
	if !m.allowRequest(modelID) {
		// 熔断器打开，直接降级
		return m.tryFallback(ctx, modelID, executor)
	}

	// 2. 尝试执行
	err := executor(modelID)
	if err == nil {
		// 成功
		m.recordSuccess(modelID)
		return nil
	}

	// 3. 失败，记录并尝试降级
	m.recordFailure(modelID)

	return m.tryFallback(ctx, modelID, executor)
}

// tryFallback 尝试降级
func (m *FallbackManager) tryFallback(
	ctx context.Context,
	originalModelID string,
	executor func(string) error,
) error {
	m.mu.RLock()
	rule, exists := m.rules[originalModelID]
	m.mu.RUnlock()

	if !exists {
		return fmt.Errorf("original request failed and no fallback rule exists")
	}

	// 遍历降级链
	for attempt := 0; attempt < len(rule.Fallbacks); attempt++ {
		fallbackModelID, err := m.GetFallback(ctx, originalModelID, attempt)
		if err != nil {
			continue
		}

		// 添加重试延迟
		if rule.RetryDelay > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(rule.RetryDelay):
			}
		}

		// 尝试执行降级模型
		err = executor(fallbackModelID)
		if err == nil {
			m.recordSuccess(fallbackModelID)
			return nil
		}

		m.recordFailure(fallbackModelID)
	}

	return fmt.Errorf("all fallback attempts failed")
}

// allowRequest 检查是否允许请求
func (m *FallbackManager) allowRequest(modelID string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	cb, exists := m.circuitBreakers[modelID]
	if !exists {
		return true
	}

	return cb.Allow()
}

// recordSuccess 记录成功
func (m *FallbackManager) recordSuccess(modelID string) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	cb, exists := m.circuitBreakers[modelID]
	if exists {
		cb.RecordSuccess()
	}
}

// recordFailure 记录失败
func (m *FallbackManager) recordFailure(modelID string) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	cb, exists := m.circuitBreakers[modelID]
	if exists {
		cb.RecordFailure()
	}
}

// GetCircuitState 获取熔断器状态
func (m *FallbackManager) GetCircuitState(modelID string) CircuitState {
	m.mu.RLock()
	defer m.mu.RUnlock()

	cb, exists := m.circuitBreakers[modelID]
	if !exists {
		return StateClosed
	}

	return cb.GetState()
}

// GetAllCircuitStates 获取所有熔断器状态
func (m *FallbackManager) GetAllCircuitStates() map[string]CircuitState {
	m.mu.RLock()
	defer m.mu.RUnlock()

	states := make(map[string]CircuitState)
	for modelID, cb := range m.circuitBreakers {
		states[modelID] = cb.GetState()
	}

	return states
}

// DisableModel 禁用模型
func (m *FallbackManager) DisableModel(modelID string) error {
	return m.registry.Disable(modelID)
}

// EnableModel 启用模型
func (m *FallbackManager) EnableModel(modelID string) error {
	return m.registry.Enable(modelID)
}
