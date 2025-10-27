package grpc

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/pkg/resilience"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
)

// ResilientClientConfig 弹性客户端配置
type ResilientClientConfig struct {
	// ServiceName 服务名称
	ServiceName string
	// Target 目标地址（可以是服务发现URL）
	Target string
	// Timeout 请求超时
	Timeout time.Duration
	// CircuitBreaker 熔断器配置
	CircuitBreaker resilience.Config
	// RetryPolicy 重试策略
	RetryPolicy resilience.RetryPolicy
	// KeepAlive 保持连接配置
	KeepAlive *KeepAliveConfig
	// MaxMessageSize 最大消息大小
	MaxMessageSize int
}

// KeepAliveConfig 保持连接配置
type KeepAliveConfig struct {
	Time                time.Duration
	Timeout             time.Duration
	PermitWithoutStream bool
}

// DefaultResilientClientConfig 默认配置
func DefaultResilientClientConfig(serviceName, target string) ResilientClientConfig {
	return ResilientClientConfig{
		ServiceName: serviceName,
		Target:      target,
		Timeout:     30 * time.Second,
		CircuitBreaker: resilience.Config{
			MaxFailures:      5,
			Timeout:          60 * time.Second,
			MaxRequests:      3,
			SuccessThreshold: 2,
		},
		RetryPolicy: resilience.RetryPolicy{
			MaxRetries:        3,
			InitialDelay:      100 * time.Millisecond,
			MaxDelay:          5 * time.Second,
			BackoffMultiplier: 2.0,
		},
		KeepAlive: &KeepAliveConfig{
			Time:                30 * time.Second,
			Timeout:             10 * time.Second,
			PermitWithoutStream: true,
		},
		MaxMessageSize: 4 * 1024 * 1024, // 4MB
	}
}

// ResilientClient 弹性gRPC客户端
type ResilientClient struct {
	conn           *grpc.ClientConn
	circuitBreaker *resilience.CircuitBreaker
	config         ResilientClientConfig
}

// NewResilientClient 创建弹性客户端
func NewResilientClient(config ResilientClientConfig) (*ResilientClient, error) {
	// 创建熔断器
	cb := resilience.NewCircuitBreaker(config.CircuitBreaker)

	// gRPC连接选项
	opts := []grpc.DialOption{
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(config.MaxMessageSize),
			grpc.MaxCallSendMsgSize(config.MaxMessageSize),
		),
	}

	// Keep-alive配置
	if config.KeepAlive != nil {
		opts = append(opts, grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                config.KeepAlive.Time,
			Timeout:             config.KeepAlive.Timeout,
			PermitWithoutStream: config.KeepAlive.PermitWithoutStream,
		}))
	}

	// 建立连接
	conn, err := grpc.NewClient(config.Target, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create grpc client: %w", err)
	}

	return &ResilientClient{
		conn:           conn,
		circuitBreaker: cb,
		config:         config,
	}, nil
}

// Invoke 调用gRPC方法（带熔断和重试）
func (c *ResilientClient) Invoke(ctx context.Context, method string, args interface{}, reply interface{}, opts ...grpc.CallOption) error {
	// 添加超时
	if c.config.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, c.config.Timeout)
		defer cancel()
	}

	// 使用重试策略
	return resilience.Retry(ctx, c.config.RetryPolicy, func() error {
		// 使用熔断器保护
		return c.circuitBreaker.Execute(ctx, func() error {
			return c.conn.Invoke(ctx, method, args, reply, opts...)
		})
	})
}

// Conn 获取底层连接
func (c *ResilientClient) Conn() *grpc.ClientConn {
	return c.conn
}

// CircuitBreakerState 获取熔断器状态
func (c *ResilientClient) CircuitBreakerState() resilience.State {
	return c.circuitBreaker.State()
}

// CircuitBreakerMetrics 获取熔断器指标
func (c *ResilientClient) CircuitBreakerMetrics() resilience.Metrics {
	return c.circuitBreaker.Metrics()
}

// Close 关闭连接
func (c *ResilientClient) Close() error {
	return c.conn.Close()
}

// ServiceClientPool 服务客户端池
type ServiceClientPool struct {
	clients map[string]*ResilientClient
}

// NewServiceClientPool 创建客户端池
func NewServiceClientPool() *ServiceClientPool {
	return &ServiceClientPool{
		clients: make(map[string]*ResilientClient),
	}
}

// GetClient 获取或创建客户端
func (p *ServiceClientPool) GetClient(serviceName, target string) (*ResilientClient, error) {
	if client, ok := p.clients[serviceName]; ok {
		return client, nil
	}

	config := DefaultResilientClientConfig(serviceName, target)
	client, err := NewResilientClient(config)
	if err != nil {
		return nil, err
	}

	p.clients[serviceName] = client
	return client, nil
}

// CloseAll 关闭所有客户端
func (p *ServiceClientPool) CloseAll() {
	for _, client := range p.clients {
		_ = client.Close()
	}
	p.clients = make(map[string]*ResilientClient)
}

