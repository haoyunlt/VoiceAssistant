package main

import (
	"time"
	"voiceassistant/cmd/knowledge-service/internal/data"
)

// Config is application config.
type Config struct {
	Server        ServerConf
	Data          DataConf
	Storage       StorageConf
	Event         EventConf
	Security      SecurityConf
	Observability ObservabilityConf
}

// ServerConf is server config.
type ServerConf struct {
	HTTP HTTPConf
	GRPC GRPCConf
}

type HTTPConf struct {
	Network string        `yaml:"network"`
	Addr    string        `yaml:"addr"`
	Timeout time.Duration `yaml:"timeout"`
}

type GRPCConf struct {
	Network string        `yaml:"network"`
	Addr    string        `yaml:"addr"`
	Timeout time.Duration `yaml:"timeout"`
}

// DataConf is data config.
type DataConf struct {
	Database data.Config `yaml:"database"`
}

// StorageConf is storage config (MinIO).
type StorageConf struct {
	Endpoint        string `yaml:"endpoint"`
	AccessKeyID     string `yaml:"access_key_id"`
	SecretAccessKey string `yaml:"secret_access_key"`
	BucketName      string `yaml:"bucket_name"`
	UseSSL          bool   `yaml:"use_ssl"`
}

// EventConf is event config (Kafka).
type EventConf struct {
	Brokers []string `yaml:"brokers"`
	Topic   string   `yaml:"topic"`
}

// SecurityConf is security config.
type SecurityConf struct {
	ClamAV ClamAVConf `yaml:"clamav"`
}

type ClamAVConf struct {
	Host    string        `yaml:"host"`
	Port    int           `yaml:"port"`
	Timeout time.Duration `yaml:"timeout"`
}

// ObservabilityConf is observability config.
type ObservabilityConf struct {
	ServiceName string `yaml:"service_name"`
	Tracing     struct {
		Endpoint   string  `yaml:"endpoint"`
		SampleRate float64 `yaml:"sample_rate"`
	} `yaml:"tracing"`
	Metrics struct {
		Endpoint string `yaml:"endpoint"`
	} `yaml:"metrics"`
}
