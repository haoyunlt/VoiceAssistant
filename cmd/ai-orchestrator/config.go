package main

import (
	"time"
)

// Config is application config.
type Config struct {
	Server   ServerConf   `json:"server" yaml:"server"`
	Data     DataConf     `json:"data" yaml:"data"`
	Services ServicesConf `json:"services" yaml:"services"`
}

// ServerConf is server config.
type ServerConf struct {
	HTTP HTTPConf `json:"http" yaml:"http"`
	GRPC GRPCConf `json:"grpc" yaml:"grpc"`
}

type HTTPConf struct {
	Network string `json:"network" yaml:"network"`
	Addr    string `json:"addr" yaml:"addr"`
	Timeout string `json:"timeout" yaml:"timeout"`
}

type GRPCConf struct {
	Network string `json:"network" yaml:"network"`
	Addr    string `json:"addr" yaml:"addr"`
	Timeout string `json:"timeout" yaml:"timeout"`
}

// DataConf is data config.
type DataConf struct {
	Database DatabaseConf `json:"database" yaml:"database"`
	Redis    RedisConf    `json:"redis" yaml:"redis"`
}

// DatabaseConf 数据库配置
type DatabaseConf struct {
	Driver          string `json:"driver" yaml:"driver"`
	Source          string `json:"source" yaml:"source"`
	MaxIdleConns    int    `json:"max_idle_conns" yaml:"max_idle_conns"`
	MaxOpenConns    int    `json:"max_open_conns" yaml:"max_open_conns"`
	ConnMaxLifetime string `json:"conn_max_lifetime" yaml:"conn_max_lifetime"`
}

// RedisConf Redis配置
type RedisConf struct {
	Addr         string `json:"addr" yaml:"addr"`
	Password     string `json:"password" yaml:"password"`
	DB           int    `json:"db" yaml:"db"`
	DialTimeout  string `json:"dial_timeout" yaml:"dial_timeout"`
	ReadTimeout  string `json:"read_timeout" yaml:"read_timeout"`
	WriteTimeout string `json:"write_timeout" yaml:"write_timeout"`
}

// ServicesConf 下游服务配置
type ServicesConf struct {
	RetrievalService ServiceEndpoint `json:"retrieval_service" yaml:"retrieval_service"`
	RAGEngine        ServiceEndpoint `json:"rag_engine" yaml:"rag_engine"`
	AgentEngine      ServiceEndpoint `json:"agent_engine" yaml:"agent_engine"`
	VoiceEngine      ServiceEndpoint `json:"voice_engine" yaml:"voice_engine"`
}

// ServiceEndpoint 服务端点配置
type ServiceEndpoint struct {
	Addr    string `json:"addr" yaml:"addr"`
	Timeout string `json:"timeout" yaml:"timeout"`
}

// ParseDuration 解析duration配置
func ParseDuration(s string) time.Duration {
	if s == "" {
		return 0
	}
	d, err := time.ParseDuration(s)
	if err != nil {
		return 0
	}
	return d
}
