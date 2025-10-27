package main

import "voiceassistant/cmd/model-router/internal/data"

type Config struct {
	Server ServerConf
	Data   DataConf
}

type ServerConf struct {
	HTTP HTTPConf
	GRPC GRPCConf
}

type HTTPConf struct {
	Addr string
}

type GRPCConf struct {
	Addr string
}

type DataConf struct {
	Database data.Config
}
