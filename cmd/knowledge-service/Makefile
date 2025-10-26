.PHONY: init build run test clean wire proto

SERVICE_NAME=knowledge-service
PROTO_PATH=../../api/proto/knowledge/v1

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
	protoc --proto_path=$(PROTO_PATH) \
		--proto_path=../../third_party \
		--go_out=paths=source_relative:$(PROTO_PATH) \
		--go-grpc_out=paths=source_relative:$(PROTO_PATH) \
		--grpc-gateway_out=paths=source_relative,grpc_api_configuration=$(PROTO_PATH)/$(SERVICE_NAME).yaml:$(PROTO_PATH) \
		$(PROTO_PATH)/*.proto

docker-build:
	docker build -t voicehelper/$(SERVICE_NAME):latest -f ../../deployments/docker/Dockerfile.go-service --build-arg SERVICE=$(SERVICE_NAME) ../..

docker-run:
	docker run -p 8000:8000 -p 9000:9000 voicehelper/$(SERVICE_NAME):latest

lint:
	golangci-lint run

coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
