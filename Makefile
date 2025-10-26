.PHONY: help lint test build deploy-dev deploy-prod e2e load proto-gen

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Linting
lint: ## Run code linters for Go, Python, and TypeScript
	@echo "==> Linting Go code..."
	@golangci-lint run ./...
	@echo "==> Linting Python code..."
	@cd algo && ruff check .
	@echo "==> Linting TypeScript code..."
	@cd platforms/web && npm run lint
	@cd platforms/admin && npm run lint

# Testing
test: ## Run unit tests
	@echo "==> Running Go unit tests..."
	@go test -v -race -coverprofile=coverage.out -covermode=atomic ./...
	@echo "==> Running Python unit tests..."
	@cd algo && pytest
	@echo "==> Running TypeScript unit tests..."
	@cd platforms/web && npm test

# Building
build: ## Build Docker images for all services
	@echo "==> Building Go services..."
	@./scripts/build.sh go
	@echo "==> Building Python services..."
	@./scripts/build.sh python
	@echo "==> Building frontend..."
	@./scripts/build.sh frontend

# Deployment
deploy-dev: ## Deploy to development environment
	@echo "==> Deploying to dev environment..."
	@./scripts/deploy/deploy.sh dev

deploy-prod: ## Deploy to production environment
	@echo "==> Deploying to prod environment..."
	@./scripts/deploy/deploy.sh prod

# E2E Testing
e2e: ## Run end-to-end tests
	@echo "==> Running E2E tests..."
	@cd tests/e2e && npm test

# Load Testing
load: ## Run load tests with k6
	@echo "==> Running load tests..."
	@k6 run tests/load/k6/conversation.js

# Proto Generation
proto-gen: ## Generate gRPC code from proto files
	@echo "==> Generating proto files..."
	@./scripts/proto-gen.sh

# Database Migration
migrate-up: ## Run database migrations (up)
	@echo "==> Running migrations..."
	@./scripts/migration/migrate.sh up

migrate-down: ## Run database migrations (down)
	@echo "==> Rolling back migrations..."
	@./scripts/migration/migrate.sh down

# Local Development
dev-up: ## Start local development environment with docker-compose
	@docker-compose up -d

dev-down: ## Stop local development environment
	@docker-compose down

dev-logs: ## Show logs from local development environment
	@docker-compose logs -f

# Clean
clean: ## Clean build artifacts
	@echo "==> Cleaning build artifacts..."
	@rm -rf coverage.out
	@rm -rf algo/htmlcov
	@rm -rf platforms/web/.next
	@rm -rf platforms/web/out
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

