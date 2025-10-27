package main

import (
	"voiceassistant/cmd/identity-service/internal/data"

	"github.com/redis/go-redis/v9"
)

// Config is application config.
type Config struct {
	Server    ServerConf
	Data      DataConf
	JWTSecret string
}

// ServerConf is server config.
type ServerConf struct {
	HTTP HTTPConf
	GRPC GRPCConf
}

type HTTPConf struct {
	Network string
	Addr    string
	Timeout string
}

type GRPCConf struct {
	Network string
	Addr    string
	Timeout string
}

// DataConf is data config.
type DataConf struct {
	Database data.Config
	Redis    RedisConf
}

type RedisConf struct {
	Addr         string
	Password     string
	DB           int
	PoolSize     int
	MinIdleConns int
	ReadTimeout  string
	WriteTimeout string
}

// NewRedisClient 创建 Redis 客户端
func NewRedisClient(conf *Config) *redis.Client {
	return redis.NewClient(&redis.Options{
		Addr:         conf.Data.Redis.Addr,
		Password:     conf.Data.Redis.Password,
		DB:           conf.Data.Redis.DB,
		PoolSize:     conf.Data.Redis.PoolSize,
		MinIdleConns: conf.Data.Redis.MinIdleConns,
	})
}
