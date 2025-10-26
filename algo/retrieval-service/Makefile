.PHONY: help install dev run test lint format docker-build docker-run clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black ruff

run: ## Run the service locally
	python main.py

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=html

lint: ## Run linter
	ruff check .

format: ## Format code
	black .
	ruff check --fix .

docker-build: ## Build Docker image
	docker build -t voicehelper/retrieval-service:latest .

docker-run: ## Run Docker container
	docker run -d \
		-p 8003:8003 \
		--name retrieval-service \
		-e MILVUS_HOST=host.docker.internal \
		-e ELASTICSEARCH_HOST=host.docker.internal \
		voicehelper/retrieval-service:latest

clean: ## Clean up
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage

# Development commands
.PHONY: logs stop restart

logs: ## View container logs
	docker logs -f retrieval-service

stop: ## Stop container
	docker stop retrieval-service
	docker rm retrieval-service

restart: stop docker-run ## Restart container
