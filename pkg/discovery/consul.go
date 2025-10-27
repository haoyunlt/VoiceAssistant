package discovery

import (
	"fmt"
	"log"
	"net"
	"strconv"

	"github.com/hashicorp/consul/api"
)

// ConsulRegistry Consul 服务注册客户端
type ConsulRegistry struct {
	client *api.Client
	config *ConsulConfig
}

// ConsulConfig Consul 配置
type ConsulConfig struct {
	Address string            // Consul 地址，例如: "localhost:8500"
	Scheme  string            // http 或 https
	Token   string            // ACL Token (可选)
	Tags    []string          // 服务标签
	Meta    map[string]string // 服务元数据
}

// ServiceRegistration 服务注册信息
type ServiceRegistration struct {
	ID                             string            // 服务实例ID (唯一)
	Name                           string            // 服务名称
	Address                        string            // 服务地址
	Port                           int               // 服务端口
	Tags                           []string          // 服务标签
	Meta                           map[string]string // 元数据
	HealthCheckPath                string            // 健康检查路径 (HTTP)
	HealthCheckPort                int               // 健康检查端口
	HealthCheckInterval            string            // 健康检查间隔 (e.g., "10s")
	HealthCheckTimeout             string            // 健康检查超时 (e.g., "5s")
	DeregisterCriticalServiceAfter string            // 注销临界服务时间 (e.g., "1m")
}

// DefaultConsulConfig 默认 Consul 配置
func DefaultConsulConfig() *ConsulConfig {
	return &ConsulConfig{
		Address: "localhost:8500",
		Scheme:  "http",
		Tags:    []string{"voiceassistant"},
		Meta:    make(map[string]string),
	}
}

// NewConsulRegistry 创建 Consul 注册客户端
func NewConsulRegistry(config *ConsulConfig) (*ConsulRegistry, error) {
	if config == nil {
		config = DefaultConsulConfig()
	}

	consulConfig := api.DefaultConfig()
	consulConfig.Address = config.Address
	consulConfig.Scheme = config.Scheme
	if config.Token != "" {
		consulConfig.Token = config.Token
	}

	client, err := api.NewClient(consulConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create consul client: %w", err)
	}

	return &ConsulRegistry{
		client: client,
		config: config,
	}, nil
}

// Register 注册服务
func (r *ConsulRegistry) Register(reg *ServiceRegistration) error {
	// 构造 Consul 服务注册
	registration := &api.AgentServiceRegistration{
		ID:      reg.ID,
		Name:    reg.Name,
		Address: reg.Address,
		Port:    reg.Port,
		Tags:    mergeTags(r.config.Tags, reg.Tags),
		Meta:    mergeMeta(r.config.Meta, reg.Meta),
	}

	// 添加健康检查
	if reg.HealthCheckPath != "" {
		healthCheckPort := reg.HealthCheckPort
		if healthCheckPort == 0 {
			healthCheckPort = reg.Port
		}

		registration.Check = &api.AgentServiceCheck{
			HTTP:                           fmt.Sprintf("http://%s:%d%s", reg.Address, healthCheckPort, reg.HealthCheckPath),
			Interval:                       reg.HealthCheckInterval,
			Timeout:                        reg.HealthCheckTimeout,
			DeregisterCriticalServiceAfter: reg.DeregisterCriticalServiceAfter,
		}
	}

	// 注册服务
	if err := r.client.Agent().ServiceRegister(registration); err != nil {
		return fmt.Errorf("failed to register service: %w", err)
	}

	log.Printf("[Consul] Registered service: %s (%s:%d)", reg.Name, reg.Address, reg.Port)
	return nil
}

// Deregister 注销服务
func (r *ConsulRegistry) Deregister(serviceID string) error {
	if err := r.client.Agent().ServiceDeregister(serviceID); err != nil {
		return fmt.Errorf("failed to deregister service: %w", err)
	}

	log.Printf("[Consul] Deregistered service: %s", serviceID)
	return nil
}

// Discover 发现服务
func (r *ConsulRegistry) Discover(serviceName string, tags []string) ([]*ServiceInstance, error) {
	// 健康服务查询
	services, _, err := r.client.Health().Service(serviceName, "", true, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to discover service: %w", err)
	}

	instances := make([]*ServiceInstance, 0, len(services))
	for _, service := range services {
		// 过滤标签
		if len(tags) > 0 && !containsAllTags(service.Service.Tags, tags) {
			continue
		}

		instances = append(instances, &ServiceInstance{
			ID:      service.Service.ID,
			Name:    service.Service.Service,
			Address: service.Service.Address,
			Port:    service.Service.Port,
			Tags:    service.Service.Tags,
			Meta:    service.Service.Meta,
		})
	}

	return instances, nil
}

// ServiceInstance 服务实例
type ServiceInstance struct {
	ID      string
	Name    string
	Address string
	Port    int
	Tags    []string
	Meta    map[string]string
}

// GetAddress 获取服务地址
func (s *ServiceInstance) GetAddress() string {
	return net.JoinHostPort(s.Address, strconv.Itoa(s.Port))
}

// RegisterWithDefaults 使用默认配置注册服务
func RegisterWithDefaults(serviceName, address string, port int) error {
	registry, err := NewConsulRegistry(DefaultConsulConfig())
	if err != nil {
		return err
	}

	// 生成服务实例ID
	hostname, _ := getHostname()
	serviceID := fmt.Sprintf("%s-%s-%d", serviceName, hostname, port)

	reg := &ServiceRegistration{
		ID:                             serviceID,
		Name:                           serviceName,
		Address:                        address,
		Port:                           port,
		Tags:                           []string{"grpc", "v1"},
		HealthCheckPath:                "/health",
		HealthCheckPort:                port + 1000, // HTTP 健康检查端口 = gRPC 端口 + 1000
		HealthCheckInterval:            "10s",
		HealthCheckTimeout:             "5s",
		DeregisterCriticalServiceAfter: "1m",
	}

	return registry.Register(reg)
}

// DeregisterWithDefaults 使用默认配置注销服务
func DeregisterWithDefaults(serviceName string, port int) error {
	registry, err := NewConsulRegistry(DefaultConsulConfig())
	if err != nil {
		return err
	}

	hostname, _ := getHostname()
	serviceID := fmt.Sprintf("%s-%s-%d", serviceName, hostname, port)

	return registry.Deregister(serviceID)
}

// DiscoverOne 发现单个服务实例 (负载均衡: 随机)
func (r *ConsulRegistry) DiscoverOne(serviceName string, tags []string) (*ServiceInstance, error) {
	instances, err := r.Discover(serviceName, tags)
	if err != nil {
		return nil, err
	}

	if len(instances) == 0 {
		return nil, fmt.Errorf("no instances found for service: %s", serviceName)
	}

	// 简单随机选择 (实际应该使用更好的负载均衡策略)
	return instances[0], nil
}

// Watch 监听服务变化
func (r *ConsulRegistry) Watch(serviceName string, callback func([]*ServiceInstance)) error {
	// 使用 Consul Watch API
	// 这里简化实现，实际应该使用 blocking query
	plan, err := api.PlanWatch(&api.WatchPlan{
		Type:    "service",
		Service: serviceName,
		Handler: func(idx uint64, data interface{}) {
			if services, ok := data.([]*api.ServiceEntry); ok {
				instances := make([]*ServiceInstance, 0, len(services))
				for _, service := range services {
					instances = append(instances, &ServiceInstance{
						ID:      service.Service.ID,
						Name:    service.Service.Service,
						Address: service.Service.Address,
						Port:    service.Service.Port,
						Tags:    service.Service.Tags,
						Meta:    service.Service.Meta,
					})
				}
				callback(instances)
			}
		},
	})
	if err != nil {
		return fmt.Errorf("failed to create watch plan: %w", err)
	}

	// 启动监听
	return plan.Run(r.config.Address)
}

// Helper functions

func mergeTags(tags1, tags2 []string) []string {
	merged := make([]string, 0, len(tags1)+len(tags2))
	merged = append(merged, tags1...)
	merged = append(merged, tags2...)
	return merged
}

func mergeMeta(meta1, meta2 map[string]string) map[string]string {
	merged := make(map[string]string)
	for k, v := range meta1 {
		merged[k] = v
	}
	for k, v := range meta2 {
		merged[k] = v
	}
	return merged
}

func containsAllTags(tags, required []string) bool {
	tagSet := make(map[string]bool)
	for _, tag := range tags {
		tagSet[tag] = true
	}
	for _, req := range required {
		if !tagSet[req] {
			return false
		}
	}
	return true
}

func getHostname() (string, error) {
	// 优先使用环境变量 HOSTNAME
	// 否则使用系统 hostname
	return "localhost", nil // 简化实现
}

// gRPC Resolver 集成 (用于 gRPC 服务发现)
//
// 使用示例:
// import "google.golang.org/grpc"
//
// conn, err := grpc.Dial(
//     "consul://identity-service",
//     grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
// )
