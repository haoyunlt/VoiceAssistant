package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// ServicesConfig 服务配置
type ServicesConfig struct {
	GRPCServices   map[string]GRPCServiceInfo `yaml:"grpc_services"`
	HTTPServices   map[string]HTTPServiceInfo `yaml:"http_services"`
	DockerServices DockerServicesConfig       `yaml:"docker_services"`
	PortReference  map[string]string          `yaml:"port_reference"`
	Notes          []string                   `yaml:"notes"`
}

// GRPCServiceInfo gRPC 服务信息
type GRPCServiceInfo struct {
	Address       string        `yaml:"address"`
	DiscoveryName string        `yaml:"discovery_name"`
	Timeout       time.Duration `yaml:"timeout"`
}

// HTTPServiceInfo HTTP 服务信息
type HTTPServiceInfo struct {
	URL         string        `yaml:"url"`
	Timeout     time.Duration `yaml:"timeout"`
	Description string        `yaml:"description"`
}

// DockerServicesConfig Docker 部署配置
type DockerServicesConfig struct {
	GRPC map[string]string `yaml:"grpc"`
	HTTP map[string]string `yaml:"http"`
}

// LoadServicesConfig 从 YAML 文件加载服务配置
func LoadServicesConfig(configPath string) (*ServicesConfig, error) {
	// 读取配置文件
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("read config file %s: %w", configPath, err)
	}

	var config ServicesConfig
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	return &config, nil
}

// LoadServicesConfigFromEnv 从环境变量或默认路径加载配置
func LoadServicesConfigFromEnv() (*ServicesConfig, error) {
	configPath := os.Getenv("SERVICES_CONFIG_PATH")
	if configPath == "" {
		configPath = "configs/services.yaml"
	}

	return LoadServicesConfig(configPath)
}

// GetGRPCServiceAddress 获取 gRPC 服务地址
func (c *ServicesConfig) GetGRPCServiceAddress(serviceName string) (string, error) {
	info, ok := c.GRPCServices[serviceName]
	if !ok {
		return "", fmt.Errorf("gRPC service %s not found in config", serviceName)
	}
	return info.Address, nil
}

// GetHTTPServiceURL 获取 HTTP 服务 URL
func (c *ServicesConfig) GetHTTPServiceURL(serviceName string) (string, error) {
	info, ok := c.HTTPServices[serviceName]
	if !ok {
		return "", fmt.Errorf("HTTP service %s not found in config", serviceName)
	}
	return info.URL, nil
}

// GetHTTPServiceURLs 获取所有 HTTP 服务 URL 映射
func (c *ServicesConfig) GetHTTPServiceURLs() map[string]string {
	urls := make(map[string]string, len(c.HTTPServices))
	for name, info := range c.HTTPServices {
		urls[name] = info.URL
	}
	return urls
}

// GetHTTPServiceTimeout 获取 HTTP 服务超时时间
func (c *ServicesConfig) GetHTTPServiceTimeout(serviceName string) (time.Duration, error) {
	info, ok := c.HTTPServices[serviceName]
	if !ok {
		return 0, fmt.Errorf("HTTP service %s not found in config", serviceName)
	}
	if info.Timeout == 0 {
		return 60 * time.Second, nil // 默认 60s
	}
	return info.Timeout, nil
}
