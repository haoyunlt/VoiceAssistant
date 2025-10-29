.PHONY: help install run test eval demo lint format clean docker-build docker-run dev deploy-dashboards

help:
	@echo "Agent Engine - Available Commands"
	@echo "=================================="
	@echo "  make install          - Install dependencies"
	@echo "  make run              - Run the application"
	@echo "  make dev              - Run in development mode"
	@echo "  make test             - Run tests"
	@echo "  make eval             - Run agent evaluation"
	@echo "  make demo             - Run observability demo"
	@echo "  make lint             - Run linters"
	@echo "  make format           - Format code"
	@echo "  make clean            - Clean up"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Run Docker container"
	@echo "  make deploy-dashboards - Deploy Grafana dashboards"

install:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8010

dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8010 --log-level debug

test:
	pytest tests/ -v

eval:
	@echo "Running Agent Evaluation..."
	python tests/eval/agent/run_evaluation.py \
		--dataset tests/eval/agent/datasets/benchmark.json \
		--modes react \
		--output tests/eval/agent/reports/result.json
	@echo "✅ Evaluation completed! Report saved to tests/eval/agent/reports/result.json"

demo:
	@echo "Running Observability Demo..."
	python examples/observability_demo.py

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf tests/eval/agent/reports/*.json 2>/dev/null || true
	@echo "✅ Cleanup completed!"

docker-build:
	docker build -t voiceassistant/agent-engine:latest .

docker-run:
	docker run -p 8010:8010 --env-file .env voiceassistant/agent-engine:latest

deploy-dashboards:
	@echo "Deploying Grafana dashboards..."
	kubectl apply -f ../../deployments/grafana/dashboards/agent-performance.json
	kubectl apply -f ../../deployments/grafana/dashboards/agent-cost.json
	kubectl apply -f ../../deployments/grafana/dashboards/agent-tracing.json
	@echo "✅ Dashboards deployed successfully!"
