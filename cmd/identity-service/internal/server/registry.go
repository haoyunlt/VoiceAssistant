package server

import (
	"fmt"
	"net"
	"os"
	"strconv"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/hashicorp/consul/api"
)

const (
	// 服务名称
	ServiceName = "identity-service"

	// 健康检查间隔
	HealthCheckInterval = "10s"
	HealthCheckTimeout  = "1s"

	// 注销延迟 (服务异常后多久注销)
	DeregisterCriticalServiceAfter = "30s"
)

// ConsulRegistry Consul 服务注册器
type ConsulRegistry struct {
	client     *api.Client
	serviceID  string
	host       string
	grpcPort   int
	httpPort   int
	logger     *log.Helper
	registered bool
}

// NewConsulRegistry 创建 Consul 注册器
func NewConsulRegistry(consulAddr string, grpcPort, httpPort int, logger log.Logger) (*ConsulRegistry, error) {
	// 创建 Consul 客户端配置
	config := api.DefaultConfig()
	config.Address = consulAddr

	// 创建客户端
	client, err := api.NewClient(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create consul client: %w", err)
	}

	// 获取主机名
	hostname, err := os.Hostname()
	if err != nil {
		hostname = "unknown"
	}

	// 生成服务 ID (唯一标识)
	serviceID := fmt.Sprintf("%s-%s-%d", ServiceName, hostname, grpcPort)

	// 获取本机 IP
	host, err := getLocalIP()
	if err != nil {
		return nil, fmt.Errorf("failed to get local IP: %w", err)
	}

	return &ConsulRegistry{
		client:    client,
		serviceID: serviceID,
		host:      host,
		grpcPort:  grpcPort,
		httpPort:  httpPort,
		logger:    log.NewHelper(logger),
	}, nil
}

// Register 注册服务到 Consul
func (r *ConsulRegistry) Register() error {
	// gRPC 健康检查
	grpcCheck := &api.AgentServiceCheck{
		CheckID:                        r.serviceID + "-grpc-check",
		Name:                           "gRPC Health Check",
		GRPC:                           fmt.Sprintf("%s:%d/grpc.health.v1.Health/Check", r.host, r.grpcPort),
		Interval:                       HealthCheckInterval,
		Timeout:                        HealthCheckTimeout,
		DeregisterCriticalServiceAfter: DeregisterCriticalServiceAfter,
	}

	// HTTP 健康检查 (备用)
	httpCheck := &api.AgentServiceCheck{
		CheckID:                        r.serviceID + "-http-check",
		Name:                           "HTTP Health Check",
		HTTP:                           fmt.Sprintf("http://%s:%d/health", r.host, r.httpPort),
		Method:                         "GET",
		Interval:                       HealthCheckInterval,
		Timeout:                        HealthCheckTimeout,
		DeregisterCriticalServiceAfter: DeregisterCriticalServiceAfter,
	}

	// 服务注册
	registration := &api.AgentServiceRegistration{
		ID:      r.serviceID,
		Name:    ServiceName,
		Port:    r.grpcPort,
		Address: r.host,
		Tags: []string{
			"grpc",
			"auth",
			"user",
			"tenant",
			"v2.0",
			"production",
		},
		Meta: map[string]string{
			"version":     "v2.0",
			"protocol":    "grpc",
			"http_port":   strconv.Itoa(r.httpPort),
			"environment": getEnvironment(),
		},
		Checks: api.AgentServiceChecks{
			grpcCheck,
			httpCheck,
		},
	}

	// 注册服务
	if err := r.client.Agent().ServiceRegister(registration); err != nil {
		return fmt.Errorf("failed to register service: %w", err)
	}

	r.registered = true
	r.logger.Infof("Service registered successfully: %s (ID: %s, Host: %s, gRPC Port: %d, HTTP Port: %d)",
		ServiceName, r.serviceID, r.host, r.grpcPort, r.httpPort)

	return nil
}

// Deregister 从 Consul 注销服务
func (r *ConsulRegistry) Deregister() error {
	if !r.registered {
		return nil
	}

	if err := r.client.Agent().ServiceDeregister(r.serviceID); err != nil {
		return fmt.Errorf("failed to deregister service: %w", err)
	}

	r.registered = false
	r.logger.Infof("Service deregistered successfully: %s (ID: %s)", ServiceName, r.serviceID)

	return nil
}

// UpdateTTL 更新健康检查 TTL (用于手动健康检查)
func (r *ConsulRegistry) UpdateTTL(checkID string, status string, output string) error {
	checkID = r.serviceID + "-" + checkID

	var err error
	switch status {
	case "passing":
		err = r.client.Agent().PassTTL(checkID, output)
	case "warning":
		err = r.client.Agent().WarnTTL(checkID, output)
	case "critical":
		err = r.client.Agent().FailTTL(checkID, output)
	default:
		return fmt.Errorf("invalid status: %s", status)
	}

	if err != nil {
		return fmt.Errorf("failed to update TTL: %w", err)
	}

	return nil
}

// GetServiceInstances 获取服务实例列表
func (r *ConsulRegistry) GetServiceInstances(serviceName string) ([]*api.ServiceEntry, error) {
	services, _, err := r.client.Health().Service(serviceName, "", true, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get service instances: %w", err)
	}

	return services, nil
}

// WatchService 监听服务变化
func (r *ConsulRegistry) WatchService(serviceName string, callback func([]*api.ServiceEntry)) error {
	// 使用 Consul 的 blocking query 监听服务变化
	var lastIndex uint64

	for {
		queryOpts := &api.QueryOptions{
			WaitIndex: lastIndex,
			WaitTime:  time.Minute,
		}

		services, meta, err := r.client.Health().Service(serviceName, "", true, queryOpts)
		if err != nil {
			r.logger.Errorf("Failed to watch service %s: %v", serviceName, err)
			time.Sleep(5 * time.Second)
			continue
		}

		// 更新索引
		if meta.LastIndex > lastIndex {
			lastIndex = meta.LastIndex
			callback(services)
		}
	}
}

// Heartbeat 发送心跳 (用于维持服务注册)
func (r *ConsulRegistry) Heartbeat(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		// 检查服务是否还在注册
		services, err := r.client.Agent().Services()
		if err != nil {
			r.logger.Errorf("Failed to get services: %v", err)
			continue
		}

		if _, exists := services[r.serviceID]; !exists {
			// 服务已被注销，重新注册
			r.logger.Warn("Service not found in consul, re-registering...")
			if err := r.Register(); err != nil {
				r.logger.Errorf("Failed to re-register service: %v", err)
			}
		}
	}
}

// SetMaintenance 设置维护模式
func (r *ConsulRegistry) SetMaintenance(enable bool, reason string) error {
	if err := r.client.Agent().EnableServiceMaintenance(r.serviceID, reason); err != nil {
		return fmt.Errorf("failed to set maintenance mode: %w", err)
	}

	if enable {
		r.logger.Infof("Service %s entered maintenance mode: %s", r.serviceID, reason)
	} else {
		r.logger.Infof("Service %s exited maintenance mode", r.serviceID)
	}

	return nil
}

// GetServiceHealth 获取服务健康状态
func (r *ConsulRegistry) GetServiceHealth() (string, error) {
	checks, err := r.client.Agent().Checks()
	if err != nil {
		return "", fmt.Errorf("failed to get checks: %w", err)
	}

	// 检查 gRPC 健康检查
	grpcCheckID := r.serviceID + "-grpc-check"
	if check, exists := checks[grpcCheckID]; exists {
		return check.Status, nil
	}

	// 检查 HTTP 健康检查
	httpCheckID := r.serviceID + "-http-check"
	if check, exists := checks[httpCheckID]; exists {
		return check.Status, nil
	}

	return "unknown", nil
}

// GetServiceInfo 获取服务信息
func (r *ConsulRegistry) GetServiceInfo() map[string]interface{} {
	return map[string]interface{}{
		"service_id":   r.serviceID,
		"service_name": ServiceName,
		"host":         r.host,
		"grpc_port":    r.grpcPort,
		"http_port":    r.httpPort,
		"registered":   r.registered,
	}
}

// ========================================
// 辅助函数
// ========================================

// getLocalIP 获取本机 IP 地址
func getLocalIP() (string, error) {
	// 如果设置了环境变量，直接使用
	if ip := os.Getenv("HOST_IP"); ip != "" {
		return ip, nil
	}

	// 获取网络接口
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return "", err
	}

	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				return ipnet.IP.String(), nil
			}
		}
	}

	return "", fmt.Errorf("no valid IP address found")
}

// getEnvironment 获取环境名称
func getEnvironment() string {
	env := os.Getenv("ENVIRONMENT")
	if env == "" {
		env = "production"
	}
	return env
}

// ========================================
// Consul KV 存储 (用于配置管理)
// ========================================

// GetConfig 从 Consul KV 获取配置
func (r *ConsulRegistry) GetConfig(key string) ([]byte, error) {
	pair, _, err := r.client.KV().Get(key, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get config: %w", err)
	}

	if pair == nil {
		return nil, fmt.Errorf("config not found: %s", key)
	}

	return pair.Value, nil
}

// SetConfig 设置 Consul KV 配置
func (r *ConsulRegistry) SetConfig(key string, value []byte) error {
	pair := &api.KVPair{
		Key:   key,
		Value: value,
	}

	if _, err := r.client.KV().Put(pair, nil); err != nil {
		return fmt.Errorf("failed to set config: %w", err)
	}

	return nil
}

// WatchConfig 监听配置变化
func (r *ConsulRegistry) WatchConfig(key string, callback func([]byte)) error {
	var lastIndex uint64

	for {
		queryOpts := &api.QueryOptions{
			WaitIndex: lastIndex,
			WaitTime:  time.Minute,
		}

		pair, meta, err := r.client.KV().Get(key, queryOpts)
		if err != nil {
			r.logger.Errorf("Failed to watch config %s: %v", key, err)
			time.Sleep(5 * time.Second)
			continue
		}

		// 更新索引
		if meta.LastIndex > lastIndex {
			lastIndex = meta.LastIndex
			if pair != nil {
				callback(pair.Value)
			}
		}
	}
}
