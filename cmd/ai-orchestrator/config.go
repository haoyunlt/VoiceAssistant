package main

import "voiceassistant/cmd/ai-orchestrator/internal/data"

// Config is application config.
type Config struct {
	Server ServerConf
	Data   DataConf
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
}
