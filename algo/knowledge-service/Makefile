.PHONY: help install test lint format clean run docker-build docker-run

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

install-dev:  ## Install development dependencies
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black ruff

test:  ## Run tests
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-unit:  ## Run unit tests only
	pytest tests/ -v -m "not integration"

test-integration:  ## Run integration tests only
	pytest tests/ -v -m "integration"

lint:  ## Run linter (ruff)
	ruff check app/ tests/

format:  ## Format code with black
	black app/ tests/
	ruff check --fix app/ tests/

clean:  ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete

run:  ## Run the service locally
	python main.py

run-dev:  ## Run with auto-reload
	uvicorn main:app --reload --host 0.0.0.0 --port 8006

docker-build:  ## Build Docker image
	docker build -t knowledge-service:latest .

docker-run:  ## Run Docker container
	docker run -p 8006:8006 --env-file .env knowledge-service:latest

health:  ## Check service health
	curl http://localhost:8006/health | jq

metrics:  ## Get service metrics (if implemented)
	curl http://localhost:8006/metrics
