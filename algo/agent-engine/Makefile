.PHONY: install run test lint clean docker-build docker-run

install:
	pip install -r requirements.txt

run:
	uvicorn main_refactored:app --reload --host 0.0.0.0 --port 8010

test:
	pytest tests/ -v

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

docker-build:
	docker build -t voiceassistant/agent-engine:latest .

docker-run:
	docker run -p 8010:8010 --env-file .env voiceassistant/agent-engine:latest

dev:
	uvicorn main_refactored:app --reload --host 0.0.0.0 --port 8010 --log-level debug
