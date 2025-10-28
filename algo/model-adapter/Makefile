# Model Adapter - Makefile (改进版)

.PHONY: help install dev test lint format clean run docker-build docker-run

# 默认目标
.DEFAULT_GOAL := help

# 变量
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
DOCKER_IMAGE := model-adapter
DOCKER_TAG := latest

help: ## 显示帮助信息
	@echo "Model Adapter - 可用命令:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

install: ## 安装生产依赖
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev: ## 安装开发依赖
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov pytest-mock black isort mypy ruff

test: ## 运行单元测试
	$(PYTEST) tests/ -v

test-cov: ## 运行测试并生成覆盖率报告
	$(PYTEST) tests/ -v --cov=app --cov-report=html --cov-report=term

test-unit: ## 只运行单元测试
	$(PYTEST) tests/ -v -m unit

test-integration: ## 只运行集成测试
	$(PYTEST) tests/ -v -m integration

lint: ## 代码检查
	@echo "Running ruff..."
	ruff check app/ tests/
	@echo "Running mypy..."
	mypy app/ --ignore-missing-imports

format: ## 格式化代码
	@echo "Running black..."
	black app/ tests/
	@echo "Running isort..."
	isort app/ tests/

format-check: ## 检查代码格式
	black app/ tests/ --check
	isort app/ tests/ --check

clean: ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml

run: ## 运行服务（开发模式）
	$(PYTHON) main.py

run-prod: ## 运行服务（生产模式）
	uvicorn main:app --host 0.0.0.0 --port 8005 --workers 4

docker-build: ## 构建Docker镜像
	docker build -f Dockerfile -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run: ## 运行Docker容器
	docker run -d \
		--name model-adapter \
		-p 8005:8005 \
		--env-file .env \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

docker-stop: ## 停止Docker容器
	docker stop model-adapter || true
	docker rm model-adapter || true

docker-logs: ## 查看Docker日志
	docker logs -f model-adapter

check-env: ## 检查环境配置
	@echo "Checking environment variables..."
	@$(PYTHON) -c "from app.core.settings import settings; print('Enabled providers:', settings.list_enabled_providers())"

migrate: ## 迁移到新版本
	@echo "=== 迁移到新版本 ==="
	@echo "1. 安装依赖..."
	$(MAKE) install
	@echo "2. 运行测试..."
	$(MAKE) test
	@echo "3. 构建Docker镜像..."
	$(MAKE) docker-build
	@echo "✅ 迁移完成！"

ci: ## CI流程（lint + test）
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test-cov

pre-commit: ## 提交前检查
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) test

all: clean install test lint ## 完整流程
