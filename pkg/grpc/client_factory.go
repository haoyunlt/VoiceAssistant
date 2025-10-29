package grpc

import (
	"context"
	"fmt"
	"sync"
	"time"

	"voicehelper/pkg/discovery"

	"google.golang.org/grpc"
)

// ClientFactory gRPC客户端工厂
// 负责创建和管理服务客户端连接池
type ClientFactory struct {
	mu       sync.RWMutex
	clients  map[string]*ResilientClient
	registry *discovery.ConsulRegistry
	config   *FactoryConfig
}

// FactoryConfig 工厂配置
type FactoryConfig struct {
	// 默认超时
	DefaultTimeout time.Duration
	// 是否启用服务发现
	EnableDiscovery bool
	// Consul 地址
	ConsulAddress string
	// 默认熔断器配置
	DefaultCircuitBreaker ResilientClientConfig
}

// DefaultFactoryConfig 默认工厂配置
func DefaultFactoryConfig() *FactoryConfig {
	return &FactoryConfig{
		DefaultTimeout:  30 * time.Second,
		EnableDiscovery: true,
		ConsulAddress:   "localhost:8500",
	}
}

// NewClientFactory 创建客户端工厂
func NewClientFactory(config *FactoryConfig) (*ClientFactory, error) {
	if config == nil {
		config = DefaultFactoryConfig()
	}

	factory := &ClientFactory{
		clients: make(map[string]*ResilientClient),
		config:  config,
	}

	// 如果启用服务发现，初始化 Consul 客户端
	if config.EnableDiscovery {
		consulConfig := &discovery.ConsulConfig{
			Address: config.ConsulAddress,
			Scheme:  "http",
		}
		registry, err := discovery.NewConsulRegistry(consulConfig)
		if err != nil {
			return nil, fmt.Errorf("failed to create consul registry: %w", err)
		}
		factory.registry = registry
	}

	return factory, nil
}

// GetClient 获取或创建服务客户端
// serviceName: 服务名称（如 identity-service）
// target: 目标地址（如果不启用服务发现，直接使用此地址）
func (f *ClientFactory) GetClient(ctx context.Context, serviceName string, target string) (*ResilientClient, error) {
	f.mu.RLock()
	if client, ok := f.clients[serviceName]; ok {
		f.mu.RUnlock()
		return client, nil
	}
	f.mu.RUnlock()

	f.mu.Lock()
	defer f.mu.Unlock()

	// 双重检查
	if client, ok := f.clients[serviceName]; ok {
		return client, nil
	}

	// 如果启用服务发现，从 Consul 获取服务地址
	if f.config.EnableDiscovery && f.registry != nil {
		instance, err := f.registry.DiscoverOne(serviceName, []string{"grpc"})
		if err == nil && instance != nil {
			target = instance.GetAddress()
		}
	}

	// 如果还是没有 target，返回错误
	if target == "" {
		return nil, fmt.Errorf("no target address found for service: %s", serviceName)
	}

	// 创建客户端配置
	config := DefaultResilientClientConfig(serviceName, target)
	if f.config.DefaultTimeout > 0 {
		config.Timeout = f.config.DefaultTimeout
	}

	// 创建客户端
	client, err := NewResilientClient(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create client for %s: %w", serviceName, err)
	}

	f.clients[serviceName] = client
	return client, nil
}

// GetClientConn 获取原生 gRPC 连接（用于生成的 proto 客户端）
func (f *ClientFactory) GetClientConn(ctx context.Context, serviceName string, target string) (*grpc.ClientConn, error) {
	client, err := f.GetClient(ctx, serviceName, target)
	if err != nil {
		return nil, err
	}
	return client.Conn(), nil
}

// CreateDirectClient 创建直连客户端（不经过服务发现）
func (f *ClientFactory) CreateDirectClient(serviceName string, target string, opts ...ClientOption) (*ResilientClient, error) {
	config := DefaultResilientClientConfig(serviceName, target)

	// 应用选项
	for _, opt := range opts {
		opt(&config)
	}

	client, err := NewResilientClient(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create direct client for %s: %w", serviceName, err)
	}

	f.mu.Lock()
	f.clients[serviceName] = client
	f.mu.Unlock()

	return client, nil
}

// Close 关闭所有客户端连接
func (f *ClientFactory) Close() error {
	f.mu.Lock()
	defer f.mu.Unlock()

	for name, client := range f.clients {
		if err := client.Close(); err != nil {
			// 记录错误但继续关闭其他客户端
			fmt.Printf("failed to close client %s: %v\n", name, err)
		}
	}

	f.clients = make(map[string]*ResilientClient)
	return nil
}

// RemoveClient 移除并关闭指定客户端
func (f *ClientFactory) RemoveClient(serviceName string) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	client, ok := f.clients[serviceName]
	if !ok {
		return nil
	}

	delete(f.clients, serviceName)
	return client.Close()
}

// HealthCheck 检查所有客户端的健康状态
func (f *ClientFactory) HealthCheck(ctx context.Context) map[string]bool {
	f.mu.RLock()
	defer f.mu.RUnlock()

	result := make(map[string]bool)
	for name, client := range f.clients {
		// 检查熔断器状态
		state := client.CircuitBreakerState()
		result[name] = state.String() == "closed"
	}

	return result
}

// GetMetrics 获取所有客户端的指标
func (f *ClientFactory) GetMetrics() map[string]interface{} {
	f.mu.RLock()
	defer f.mu.RUnlock()

	metrics := make(map[string]interface{})
	for name, client := range f.clients {
		cbMetrics := client.CircuitBreakerMetrics()
		metrics[name] = map[string]interface{}{
			"state":          client.CircuitBreakerState().String(),
			"failure_count":  cbMetrics.FailureCount,
			"success_count":  cbMetrics.SuccessCount,
		}
	}

	return metrics
}

// ClientOption 客户端选项函数
type ClientOption func(*ResilientClientConfig)

// WithTimeout 设置超时
func WithTimeout(timeout time.Duration) ClientOption {
	return func(c *ResilientClientConfig) {
		c.Timeout = timeout
	}
}

// WithMaxRetries 设置最大重试次数
func WithMaxRetries(maxRetries int) ClientOption {
	return func(c *ResilientClientConfig) {
		c.RetryPolicy.MaxRetries = maxRetries
	}
}

// WithCircuitBreakerThreshold 设置熔断器阈值
func WithCircuitBreakerThreshold(maxFailures uint32) ClientOption {
	return func(c *ResilientClientConfig) {
		c.CircuitBreaker.MaxFailures = int64(maxFailures)
	}
}

// WithKeepAlive 设置保持连接参数
func WithKeepAlive(time, timeout time.Duration) ClientOption {
	return func(c *ResilientClientConfig) {
		c.KeepAlive = &KeepAliveConfig{
			Time:                time,
			Timeout:             timeout,
			PermitWithoutStream: true,
		}
	}
}

// SimpleClientFactory 全局简单工厂实例
var (
	globalFactory     *ClientFactory
	globalFactoryOnce sync.Once
)

// GetGlobalFactory 获取全局客户端工厂
func GetGlobalFactory() *ClientFactory {
	globalFactoryOnce.Do(func() {
		factory, err := NewClientFactory(DefaultFactoryConfig())
		if err != nil {
			panic(fmt.Sprintf("failed to create global client factory: %v", err))
		}
		globalFactory = factory
	})
	return globalFactory
}

// InitGlobalFactory 初始化全局客户端工厂（带自定义配置）
func InitGlobalFactory(config *FactoryConfig) error {
	factory, err := NewClientFactory(config)
	if err != nil {
		return err
	}
	globalFactory = factory
	return nil
}
