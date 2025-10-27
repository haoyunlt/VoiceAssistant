.PHONY: all build run test clean wire proto

# Variables
SERVICE_NAME=notification-service
MAIN_FILE=main.go
BINARY_NAME=$(SERVICE_NAME)
CONFIG_FILE=../../configs/notification-service.yaml

# Build
all: wire build

build:
	@echo "Building $(SERVICE_NAME)..."
	go build -o $(BINARY_NAME) $(MAIN_FILE)

# Generate wire code
wire:
	@echo "Generating wire code..."
	cd $(shell pwd) && wire

# Run
run: wire
	@echo "Running $(SERVICE_NAME)..."
	go run . -conf $(CONFIG_FILE)

# Test
test:
	@echo "Running tests..."
	go test -v ./...

# Test with coverage
coverage:
	@echo "Running tests with coverage..."
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out

# Clean
clean:
	@echo "Cleaning..."
	rm -f $(BINARY_NAME)
	rm -f wire_gen.go
	rm -f coverage.out

# Install dependencies
deps:
	@echo "Installing dependencies..."
	go mod download
	go install github.com/google/wire/cmd/wire@latest

# Format code
fmt:
	@echo "Formatting code..."
	go fmt ./...

# Lint
lint:
	@echo "Linting code..."
	golangci-lint run

# Proto generation (when proto files are ready)
proto:
	@echo "Generating proto code..."
	# TODO: Add proto generation command

# Docker
docker-build:
	@echo "Building Docker image..."
	docker build -t $(SERVICE_NAME):latest -f Dockerfile ../..

docker-run:
	@echo "Running Docker container..."
	docker run -p 8005:8005 -p 9005:9005 $(SERVICE_NAME):latest

# Help
help:
	@echo "Available targets:"
	@echo "  all          - Generate wire code and build"
	@echo "  build        - Build the service"
	@echo "  wire         - Generate wire dependency injection code"
	@echo "  run          - Run the service locally"
	@echo "  test         - Run tests"
	@echo "  coverage     - Run tests with coverage report"
	@echo "  clean        - Clean build artifacts"
	@echo "  deps         - Install dependencies"
	@echo "  fmt          - Format code"
	@echo "  lint         - Run linter"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
