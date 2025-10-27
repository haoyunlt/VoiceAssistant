.PHONY: help verify test build deploy clean

help: ## 显示帮助信息
	@echo "VoiceAssistant - 可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

verify: ## 验证架构优化
	@echo "🔍 验证服务集成..."
	@./scripts/verify-integration.sh

test: ## 测试服务集成
	@echo "🧪 测试服务..."
	@./scripts/test-services.sh

proto-gen: ## 生成protobuf代码
	@echo "📝 生成protobuf..."
	@./scripts/proto-gen.sh

build-go: ## 编译Go服务
	@echo "🔨 编译Go服务..."
	@cd cmd/knowledge-service && go build -o ../../bin/knowledge-service
	@cd cmd/conversation-service && go build -o ../../bin/conversation-service
	@cd cmd/identity-service && go build -o ../../bin/identity-service
	@cd cmd/ai-orchestrator && go build -o ../../bin/ai-orchestrator
	@cd cmd/analytics-service && go build -o ../../bin/analytics-service
	@cd cmd/model-router && go build -o ../../bin/model-router
	@cd cmd/notification-service && go build -o ../../bin/notification-service

build-docker: ## 构建Docker镜像
	@echo "🐳 构建Docker镜像..."
	@docker-compose build

up: ## 启动所有服务
	@echo "🚀 启动服务..."
	@docker-compose up -d

down: ## 停止所有服务
	@echo "🛑 停止服务..."
	@docker-compose down

logs: ## 查看日志
	@docker-compose logs -f

ps: ## 查看服务状态
	@docker-compose ps

clean: ## 清理
	@echo "🧹 清理..."
	@rm -rf bin/
	@docker-compose down -v

deploy: verify build-docker ## 部署（验证+构建+启动）
	@echo "📦 部署中..."
	@docker-compose up -d
	@echo "✅ 部署完成"

# 开发相关
dev-agent: ## 开发模式运行Agent Engine
	@cd algo/agent-engine && python main.py

dev-rag: ## 开发模式运行RAG Engine
	@cd algo/rag-engine && python main.py

dev-retrieval: ## 开发模式运行Retrieval Service
	@cd algo/retrieval-service && python main.py

# 数据库迁移
migrate-up: ## 执行数据库迁移
	@echo "📊 执行数据库迁移..."
	@psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/001_init.sql
	@psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/002_conversations.sql
	@psql -h localhost -U voicehelper -d voicehelper -f migrations/postgres/003_knowledge.sql

# Lint相关
lint-python: ## Python代码检查
	@echo "🔍 Python代码检查..."
	@cd algo && find . -name "*.py" -not -path "./__pycache__/*" | xargs ruff check || true

lint-go: ## Go代码检查
	@echo "🔍 Go代码检查..."
	@cd cmd && golangci-lint run ./... || true

format-python: ## 格式化Python代码
	@echo "✨ 格式化Python代码..."
	@cd algo && find . -name "*.py" -not -path "./__pycache__/*" | xargs ruff format || true

format-go: ## 格式化Go代码
	@echo "✨ 格式化Go代码..."
	@cd cmd && go fmt ./...
