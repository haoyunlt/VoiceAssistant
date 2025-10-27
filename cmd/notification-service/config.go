package main

import "voiceassistant/cmd/notification-service/internal/data"

// Config is the application configuration
type Config struct {
	Server       ServerConf       `json:"server"`
	Data         DataConf         `json:"data"`
	Notification NotificationConf `json:"notification"`
}

// ServerConf is the server configuration
type ServerConf struct {
	HTTP HTTPConf `json:"http"`
	GRPC GRPCConf `json:"grpc"`
}

// HTTPConf is the HTTP server configuration
type HTTPConf struct {
	Addr    string `json:"addr"`
	Timeout int    `json:"timeout"` // seconds
}

// GRPCConf is the GRPC server configuration
type GRPCConf struct {
	Addr    string `json:"addr"`
	Timeout int    `json:"timeout"` // seconds
}

// DataConf is the data configuration
type DataConf struct {
	Database data.Config `json:"database"`
	Redis    RedisConf   `json:"redis"`
}

// RedisConf is the Redis configuration
type RedisConf struct {
	Addr     string `json:"addr"`
	Password string `json:"password"`
	DB       int    `json:"db"`
}

// NotificationConf is the notification configuration
type NotificationConf struct {
	MaxRetries    int    `json:"max_retries"`
	RetryInterval int    `json:"retry_interval"` // seconds
	EmailFrom     string `json:"email_from"`
	SMSProvider   string `json:"sms_provider"`
}
