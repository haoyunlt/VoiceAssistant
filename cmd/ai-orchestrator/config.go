package main

import "time"

// Config is application config.
type Config struct {
	Server   ServerConf   `json:"server"`
	Data     DataConf     `json:"data"`
	Services ServicesConf `json:"services"`
}

// ServerConf is server config.
type ServerConf struct {
	HTTP HTTPConf `json:"http"`
	GRPC GRPCConf `json:"grpc"`
}

type HTTPConf struct {
	Network string        `json:"network"`
	Addr    string        `json:"addr"`
	Timeout time.Duration `json:"timeout"`
}

type GRPCConf struct {
	Network string        `json:"network"`
	Addr    string        `json:"addr"`
	Timeout time.Duration `json:"timeout"`
}

// DataConf is data config.
type DataConf struct {
	Database DatabaseConf `json:"database"`
	Redis    RedisConf    `json:"redis"`
}

// DatabaseConf 数据库配置
type DatabaseConf struct {
	Driver          string        `json:"driver"`
	Source          string        `json:"source"`
	MaxIdleConns    int           `json:"max_idle_conns"`
	MaxOpenConns    int           `json:"max_open_conns"`
	ConnMaxLifetime time.Duration `json:"conn_max_lifetime"`
}

// RedisConf Redis配置
type RedisConf struct {
	Addr         string        `json:"addr"`
	Password     string        `json:"password"`
	DB           int           `json:"db"`
	DialTimeout  time.Duration `json:"dial_timeout"`
	ReadTimeout  time.Duration `json:"read_timeout"`
	WriteTimeout time.Duration `json:"write_timeout"`
}

// ServicesConf 下游服务配置
type ServicesConf struct {
	RetrievalService ServiceEndpoint `json:"retrieval_service"`
	RAGEngine        ServiceEndpoint `json:"rag_engine"`
	AgentEngine      ServiceEndpoint `json:"agent_engine"`
	VoiceEngine      ServiceEndpoint `json:"voice_engine"`
}

// ServiceEndpoint 服务端点配置
type ServiceEndpoint struct {
	Addr    string        `json:"addr"`
	Timeout time.Duration `json:"timeout"`
}
