package discovery

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc/resolver"
)

// ConsulResolver gRPC resolver for Consul
// 实现 gRPC 服务发现与负载均衡
type ConsulResolver struct {
	target      resolver.Target
	cc          resolver.ClientConn
	registry    *ConsulRegistry
	serviceName string
	tags        []string

	// 解析结果缓存
	mu        sync.RWMutex
	instances []*ServiceInstance

	// 监听控制
	stopCh chan struct{}
	closed bool
}

// NewConsulResolver 创建 Consul resolver
func NewConsulResolver(target resolver.Target, cc resolver.ClientConn, registry *ConsulRegistry) (*ConsulResolver, error) {
	// 解析目标地址：consul://service-name?tag=grpc&tag=v1
	serviceName := target.Endpoint()
	if serviceName == "" {
		return nil, fmt.Errorf("invalid target endpoint: %s", target.URL.String())
	}

	// 解析查询参数中的标签
	tags := []string{}
	if target.URL.Query().Has("tag") {
		tags = target.URL.Query()["tag"]
	}

	r := &ConsulResolver{
		target:      target,
		cc:          cc,
		registry:    registry,
		serviceName: serviceName,
		tags:        tags,
		stopCh:      make(chan struct{}),
	}

	// 启动服务发现
	go r.watcher()

	return r, nil
}

// ResolveNow 立即解析服务地址
func (r *ConsulResolver) ResolveNow(resolver.ResolveNowOptions) {
	r.resolve()
}

// Close 关闭 resolver
func (r *ConsulResolver) Close() {
	r.mu.Lock()
	defer r.mu.Unlock()

	if !r.closed {
		close(r.stopCh)
		r.closed = true
	}
}

// resolve 解析服务实例
func (r *ConsulResolver) resolve() {
	instances, err := r.registry.Discover(r.serviceName, r.tags)
	if err != nil {
		r.cc.ReportError(fmt.Errorf("failed to discover service %s: %w", r.serviceName, err))
		return
	}

	// 转换为 gRPC 地址列表
	addrs := make([]resolver.Address, 0, len(instances))
	for _, instance := range instances {
		addrs = append(addrs, resolver.Address{
			Addr:       instance.GetAddress(),
			ServerName: instance.Name,
			Metadata:   instance.Meta,
		})
	}

	// 更新缓存
	r.mu.Lock()
	r.instances = instances
	r.mu.Unlock()

	// 通知 gRPC 更新地址列表
	r.cc.UpdateState(resolver.State{
		Addresses: addrs,
	})
}

// watcher 监听服务变化
func (r *ConsulResolver) watcher() {
	ticker := time.NewTicker(10 * time.Second) // 每10秒刷新一次
	defer ticker.Stop()

	// 首次解析
	r.resolve()

	for {
		select {
		case <-r.stopCh:
			return
		case <-ticker.C:
			r.resolve()
		}
	}
}

// ConsulResolverBuilder gRPC resolver builder
type ConsulResolverBuilder struct {
	registry *ConsulRegistry
}

// NewConsulResolverBuilder 创建 resolver builder
func NewConsulResolverBuilder(registry *ConsulRegistry) *ConsulResolverBuilder {
	return &ConsulResolverBuilder{
		registry: registry,
	}
}

// Build 构建 resolver
func (b *ConsulResolverBuilder) Build(target resolver.Target, cc resolver.ClientConn, opts resolver.BuildOptions) (resolver.Resolver, error) {
	return NewConsulResolver(target, cc, b.registry)
}

// Scheme 返回 scheme
func (b *ConsulResolverBuilder) Scheme() string {
	return "consul"
}

// RegisterConsulResolver 注册 Consul resolver 到 gRPC
func RegisterConsulResolver(consulAddress string) error {
	registry, err := NewConsulRegistry(&ConsulConfig{
		Address: consulAddress,
		Scheme:  "http",
	})
	if err != nil {
		return fmt.Errorf("failed to create consul registry: %w", err)
	}

	builder := NewConsulResolverBuilder(registry)
	resolver.Register(builder)

	return nil
}

// ParseConsulTarget 解析 Consul 目标地址
// 格式: consul://service-name?tag=grpc&tag=v1
func ParseConsulTarget(target string) (serviceName string, tags []string, err error) {
	if !strings.HasPrefix(target, "consul://") {
		return "", nil, fmt.Errorf("invalid consul target: %s", target)
	}

	parts := strings.SplitN(strings.TrimPrefix(target, "consul://"), "?", 2)
	serviceName = parts[0]

	if len(parts) == 2 {
		// 解析标签
		for _, param := range strings.Split(parts[1], "&") {
			if strings.HasPrefix(param, "tag=") {
				tags = append(tags, strings.TrimPrefix(param, "tag="))
			}
		}
	}

	return serviceName, tags, nil
}

// BuildConsulTarget 构建 Consul 目标地址
func BuildConsulTarget(serviceName string, tags ...string) string {
	target := fmt.Sprintf("consul://%s", serviceName)
	if len(tags) > 0 {
		target += "?tag=" + strings.Join(tags, "&tag=")
	}
	return target
}
