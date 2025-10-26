.PHONY: help build run test wire proto clean

help: ## 显示帮助信息
	@echo 'Identity Service Makefile'
	@echo ''
	@echo 'Usage:'
	@echo '  make <target>'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## 构建服务
	@echo "Building identity-service..."
	go build -o bin/identity-service main.go main_new.go wire.go

run: ## 运行服务
	@echo "Running identity-service..."
	go run .

test: ## 运行测试
	@echo "Running tests..."
	go test -v ./internal/...

wire: ## 生成 Wire 代码
	@echo "Generating Wire code..."
	wire

proto: ## 生成 Proto 代码
	@echo "Generating Proto code..."
	cd ../.. && make proto-gen

clean: ## 清理构建文件
	@echo "Cleaning..."
	rm -f bin/identity-service
	rm -f wire_gen.go

install-tools: ## 安装开发工具
	@echo "Installing tools..."
	go install github.com/google/wire/cmd/wire@latest
	go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

mod: ## 下载依赖
	@echo "Downloading dependencies..."
	go mod download
	go mod tidy

lint: ## 代码检查
	@echo "Linting..."
	golangci-lint run

.DEFAULT_GOAL := help
