.PHONY: install run test lint clean docker-build docker-run

install:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8005

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
	docker build -t voicehelper/model-adapter:latest .

docker-run:
	docker run -p 8005:8005 --env-file .env voicehelper/model-adapter:latest

dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8005 --log-level debug
