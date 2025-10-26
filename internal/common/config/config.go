package config

import (
	"time"
)

// ServerConfig is the server configuration.
type ServerConfig struct {
	HTTP HTTPConfig `json:"http"`
	GRPC GRPCConfig `json:"grpc"`
}

// HTTPConfig is the HTTP server configuration.
type HTTPConfig struct {
	Network string        `json:"network"`
	Addr    string        `json:"addr"`
	Timeout time.Duration `json:"timeout"`
}

// GRPCConfig is the gRPC server configuration.
type GRPCConfig struct {
	Network string        `json:"network"`
	Addr    string        `json:"addr"`
	Timeout time.Duration `json:"timeout"`
}

// DataConfig is the data layer configuration.
type DataConfig struct {
	Database DatabaseConfig `json:"database"`
	Redis    RedisConfig    `json:"redis"`
}

// DatabaseConfig is the database configuration.
type DatabaseConfig struct {
	Driver string `json:"driver"`
	Source string `json:"source"`
}

// RedisConfig is the Redis configuration.
type RedisConfig struct {
	Addr         string        `json:"addr"`
	Password     string        `json:"password"`
	DB           int           `json:"db"`
	ReadTimeout  time.Duration `json:"read_timeout"`
	WriteTimeout time.Duration `json:"write_timeout"`
}

// TraceConfig is the tracing configuration.
type TraceConfig struct {
	Endpoint string `json:"endpoint"`
}
