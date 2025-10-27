package main

import (
	"voiceassistant/cmd/identity-service/internal/data"

	"github.com/redis/go-redis/v9"
)

// Config is application config.
type Config struct {
	Server    ServerConf
	Data      DataConf
	Auth      AuthConf
}

// AuthConf 认证配置
type AuthConf struct {
	JWTSecret            string
	AccessTokenExpiry    string // 如 "1h"
	RefreshTokenExpiry   string // 如 "168h" (7天)
	PasswordPolicy       PasswordPolicyConf
}

// PasswordPolicyConf 密码策略配置
type PasswordPolicyConf struct {
	MinLength      int
	RequireUpper   bool
	RequireLower   bool
	RequireDigit   bool
	RequireSpecial bool
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

// ProvideDataConfig provides data config from main config
func ProvideDataConfig(conf *Config) *data.Config {
	return &conf.Data.Database
}

// ProvideServerConf provides server config from main config
func ProvideServerConf(conf *Config) *ServerConf {
	return &conf.Server
}
