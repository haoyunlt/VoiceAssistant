package main

import (
	"time"

	"voicehelper/cmd/model-router/internal/data"
)

// Config 应用配置
type Config struct {
	Server       ServerConf       `yaml:"server"`
	Data         DataConf         `yaml:"data"`
	Models       ModelsConf       `yaml:"models"`
	Observability ObservabilityConf `yaml:"observability"`
}

// ServerConf 服务器配置
type ServerConf struct {
	HTTP HTTPConf `yaml:"http"`
	GRPC GRPCConf `yaml:"grpc"`
}

// HTTPConf HTTP服务器配置
type HTTPConf struct {
	Addr         string        `yaml:"addr"`
	Timeout      time.Duration `yaml:"timeout"`
	ReadTimeout  time.Duration `yaml:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout"`
}

// GRPCConf gRPC服务器配置
type GRPCConf struct {
	Addr    string        `yaml:"addr"`
	Timeout time.Duration `yaml:"timeout"`
}

// DataConf 数据层配置
type DataConf struct {
	Database data.Config `yaml:"database"`
	Redis    RedisConf   `yaml:"redis"`
}

// RedisConf Redis配置
type RedisConf struct {
	Addr         string        `yaml:"addr"`
	Password     string        `yaml:"password"`
	DB           int           `yaml:"db"`
	DialTimeout  time.Duration `yaml:"dial_timeout"`
	ReadTimeout  time.Duration `yaml:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout"`
}

// ModelsConf 模型配置
type ModelsConf struct {
	ConfigPath        string        `yaml:"config_path"`         // 模型配置文件路径
	HealthCheckPeriod time.Duration `yaml:"health_check_period"` // 健康检查周期
	EnableABTest      bool          `yaml:"enable_ab_test"`      // 是否启用A/B测试
}

// ObservabilityConf 可观测性配置
type ObservabilityConf struct {
	Tracing TracingConf `yaml:"tracing"`
	Metrics MetricsConf `yaml:"metrics"`
	Logging LoggingConf `yaml:"logging"`
}

// TracingConf 链路追踪配置
type TracingConf struct {
	Enabled  bool    `yaml:"enabled"`
	Endpoint string  `yaml:"endpoint"`
	Sampler  float64 `yaml:"sampler"` // 采样率 0-1
}

// MetricsConf 指标配置
type MetricsConf struct {
	Enabled bool   `yaml:"enabled"`
	Port    int    `yaml:"port"`
	Path    string `yaml:"path"`
}

// LoggingConf 日志配置
type LoggingConf struct {
	Level  string `yaml:"level"`  // debug, info, warn, error
	Format string `yaml:"format"` // json, text
}
