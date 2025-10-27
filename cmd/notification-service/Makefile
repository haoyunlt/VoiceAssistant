.PHONY: init build run test clean wire

SERVICE_NAME=notification-service

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

docker-build:
	docker build -t voiceassistant/$(SERVICE_NAME):latest -f ../../deployments/docker/Dockerfile.go-service --build-arg SERVICE=$(SERVICE_NAME) ../..

lint:
	golangci-lint run
