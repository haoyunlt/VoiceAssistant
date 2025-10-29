package clients

import (
	"fmt"
	"time"

	"voicehelper/pkg/clients"
	"voicehelper/pkg/config"
	"voicehelper/pkg/discovery"
)

// ServiceClientConfig 服务客户端配置
type ServiceClientConfig struct {
	// 客户端工厂配置
	ClientFactory struct {
		DefaultTimeout  time.Duration `yaml:"default_timeout"`
		EnableDiscovery bool          `yaml:"enable_discovery"`
		Consul          ConsulConfig  `yaml:"consul"`
	} `yaml:"client_factory"`

	// 服务地址配置
	Services map[string]ServiceConfig `yaml:"services"`

	// 拦截器配置
	Interceptors InterceptorsConfig `yaml:"interceptors"`

	// 负载均衡配置
	LoadBalancing LoadBalancingConfig `yaml:"load_balancing"`
}

// ConsulConfig Consul 配置
type ConsulConfig struct {
	Address string `yaml:"address"`
	Scheme  string `yaml:"scheme"`
	Token   string `yaml:"token"`
}

// ServiceConfig 单个服务配置
type ServiceConfig struct {
	Address        string               `yaml:"address"`
	DiscoveryName  string               `yaml:"discovery_name"`
	Tags           []string             `yaml:"tags"`
	Timeout        time.Duration        `yaml:"timeout"`
	CircuitBreaker CircuitBreakerConfig `yaml:"circuit_breaker"`
	Retry          RetryConfig          `yaml:"retry"`
	KeepAlive      KeepAliveConfig      `yaml:"keep_alive"`
}

// CircuitBreakerConfig 熔断器配置
type CircuitBreakerConfig struct {
	MaxFailures      uint32        `yaml:"max_failures"`
	Timeout          time.Duration `yaml:"timeout"`
	MaxRequests      uint32        `yaml:"max_requests"`
	SuccessThreshold uint32        `yaml:"success_threshold"`
}

// RetryConfig 重试配置
type RetryConfig struct {
	MaxRetries        int           `yaml:"max_retries"`
	InitialDelay      time.Duration `yaml:"initial_delay"`
	MaxDelay          time.Duration `yaml:"max_delay"`
	BackoffMultiplier float64       `yaml:"backoff_multiplier"`
}

// KeepAliveConfig Keep-Alive 配置
type KeepAliveConfig struct {
	Time                time.Duration `yaml:"time"`
	Timeout             time.Duration `yaml:"timeout"`
	PermitWithoutStream bool          `yaml:"permit_without_stream"`
}

// InterceptorsConfig 拦截器配置
type InterceptorsConfig struct {
	EnableTracing bool `yaml:"enable_tracing"`
	EnableAuth    bool `yaml:"enable_auth"`
	EnableLogging bool `yaml:"enable_logging"`
	EnableMetrics bool `yaml:"enable_metrics"`
}

// LoadBalancingConfig 负载均衡配置
type LoadBalancingConfig struct {
	Policy string `yaml:"policy"`
}

// InitServiceClients 初始化服务客户端
func InitServiceClients(configPath string) (*clients.ClientManager, error) {
	// 加载配置
	var cfg ServiceClientConfig
	cfgMgr := config.NewManager()
	if err := cfgMgr.LoadConfig(configPath, "services-client"); err != nil {
		return nil, fmt.Errorf("failed to load client config: %w", err)
	}
	if err := cfgMgr.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal client config: %w", err)
	}

	// 如果启用服务发现，注册 Consul resolver
	if cfg.ClientFactory.EnableDiscovery {
		consulAddr := cfg.ClientFactory.Consul.Address
		if consulAddr == "" {
			consulAddr = "localhost:8500"
		}
		if err := discovery.RegisterConsulResolver(consulAddr); err != nil {
			return nil, fmt.Errorf("failed to register consul resolver: %w", err)
		}
	}

	// 构建客户端配置
	clientConfig := &clients.ClientConfig{
		EnableDiscovery: cfg.ClientFactory.EnableDiscovery,
		ConsulAddress:   cfg.ClientFactory.Consul.Address,
		Services:        make(map[string]string),
	}

	// 设置服务地址
	for name, svcCfg := range cfg.Services {
		if cfg.ClientFactory.EnableDiscovery && svcCfg.DiscoveryName != "" {
			// 使用服务发现地址
			clientConfig.Services[name] = discovery.BuildConsulTarget(
				svcCfg.DiscoveryName,
				svcCfg.Tags...,
			)
		} else {
			// 使用直连地址
			clientConfig.Services[name] = svcCfg.Address
		}
	}

	// 创建客户端管理器
	return clients.NewClientManager(clientConfig)
}

// InitGlobalServiceClients 初始化全局服务客户端
func InitGlobalServiceClients(configPath string) error {
	manager, err := InitServiceClients(configPath)
	if err != nil {
		return err
	}

	// 将客户端管理器设置为全局单例
	// 这里可以通过 context 或其他方式传递
	_ = manager

	return nil
}

// MustInitServiceClients 初始化服务客户端（panic on error）
func MustInitServiceClients(configPath string) *clients.ClientManager {
	manager, err := InitServiceClients(configPath)
	if err != nil {
		panic(fmt.Sprintf("failed to init service clients: %v", err))
	}
	return manager
}

// DefaultServiceClients 创建默认服务客户端管理器
func DefaultServiceClients() *clients.ClientManager {
	manager, err := clients.NewClientManager(clients.DefaultClientConfig())
	if err != nil {
		panic(fmt.Sprintf("failed to create default client manager: %v", err))
	}
	return manager
}

// ClientManagerFromConfig 从配置创建客户端管理器
func ClientManagerFromConfig(cfg *ServiceClientConfig) (*clients.ClientManager, error) {
	clientConfig := &clients.ClientConfig{
		EnableDiscovery: cfg.ClientFactory.EnableDiscovery,
		ConsulAddress:   cfg.ClientFactory.Consul.Address,
		Services:        make(map[string]string),
	}

	for name, svcCfg := range cfg.Services {
		if cfg.ClientFactory.EnableDiscovery && svcCfg.DiscoveryName != "" {
			clientConfig.Services[name] = discovery.BuildConsulTarget(
				svcCfg.DiscoveryName,
				svcCfg.Tags...,
			)
		} else {
			clientConfig.Services[name] = svcCfg.Address
		}
	}

	return clients.NewClientManager(clientConfig)
}
