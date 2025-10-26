.PHONY: all build run test clean wire proto

# 项目变量
SERVICE_NAME=conversation-service
GO_FILES=$(shell find . -name '*.go' -type f)

all: wire build

# Wire 依赖注入
wire:
	@echo "Generating Wire code..."
	cd $(shell pwd) && wire

# 构建
build: wire
	@echo "Building $(SERVICE_NAME)..."
	go build -o bin/$(SERVICE_NAME) .

# 运行
run: build
	@echo "Running $(SERVICE_NAME)..."
	./bin/$(SERVICE_NAME)

# 测试
test:
	@echo "Running tests..."
	go test -v ./...

# 清理
clean:
	@echo "Cleaning..."
	rm -rf bin/
	rm -f wire_gen.go

# Docker
docker-build:
	docker build -t voicehelper/$(SERVICE_NAME):latest -f ../../deployments/docker/Dockerfile.go-service .

docker-run:
	docker run -d \
		-p 8080:8080 \
		--name $(SERVICE_NAME) \
		-e DB_HOST=postgres \
		voicehelper/$(SERVICE_NAME):latest
