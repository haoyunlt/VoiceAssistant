.PHONY: init build run test clean wire proto

SERVICE_NAME=model-router

init:
	go mod download

build:
	go build -o bin/$(SERVICE_NAME) .

run:
	go run . -conf ../../configs/app/$(SERVICE_NAME).yaml

test:
	go test -v ./...

clean:
	rm -rf bin/

wire:
	cd cmd/$(SERVICE_NAME) && wire

proto:
	@echo "Generating protobuf files..."

docker-build:
	docker build -t voiceassistant/$(SERVICE_NAME):latest -f ../../deployments/docker/Dockerfile.go-service --build-arg SERVICE=$(SERVICE_NAME) ../..

docker-run:
	docker run -p 8000:8000 -p 9000:9000 voiceassistant/$(SERVICE_NAME):latest

lint:
	golangci-lint run

coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
