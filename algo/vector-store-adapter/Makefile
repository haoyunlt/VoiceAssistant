.PHONY: install run dev test docker-build docker-run clean

install:
	pip install -r requirements.txt

run:
	python main.py

dev:
	RELOAD=true python main.py

test:
	pytest tests/ -v

docker-build:
	docker build -t vector-store-adapter:latest .

docker-run:
	docker run -p 8003:8003 \
		-e MILVUS_HOST=localhost \
		-e MILVUS_PORT=19530 \
		-e PGVECTOR_HOST=localhost \
		-e PGVECTOR_PORT=5432 \
		vector-store-adapter:latest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
