#!/usr/bin/env bash

set -euo pipefail

# Proto generation script for VoiceAssistant
# Generates Go gRPC code and OpenAPI specs from proto files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${PROJECT_ROOT}/api/proto"

echo "==> Generating protobuf code..."

# Check required tools
check_tools() {
    local missing_tools=()
    
    if ! command -v protoc &> /dev/null; then
        missing_tools+=("protoc")
    fi
    
    if ! command -v protoc-gen-go &> /dev/null; then
        missing_tools+=("protoc-gen-go")
    fi
    
    if ! command -v protoc-gen-go-grpc &> /dev/null; then
        missing_tools+=("protoc-gen-go-grpc")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo "Error: Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Please install:"
        echo "  brew install protobuf"
        echo "  go install google.golang.org/protobuf/cmd/protoc-gen-go@latest"
        echo "  go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest"
        exit 1
    fi
}

# Generate proto for a service
generate_service_proto() {
    local service_name=$1
    local proto_dir="${API_DIR}/${service_name}/v1"
    
    if [ ! -d "${proto_dir}" ]; then
        echo "  Skipping ${service_name} (no proto files found)"
        return
    fi
    
    echo "  -> Generating ${service_name}..."
    
    protoc \
        --proto_path="${API_DIR}" \
        --proto_path="${PROJECT_ROOT}/third_party" \
        --go_out="${PROJECT_ROOT}" \
        --go_opt=paths=source_relative \
        --go-grpc_out="${PROJECT_ROOT}" \
        --go-grpc_opt=paths=source_relative \
        "${proto_dir}"/*.proto
}

check_tools

# Generate for all services
SERVICES=(
    "identity"
    "conversation"
    "knowledge"
    "orchestrator"
    "router"
    "notification"
    "analytics"
)

for service in "${SERVICES[@]}"; do
    generate_service_proto "${service}"
done

echo ""
echo "✓ Proto generation completed successfully!"
echo ""
echo "Generated files in: ${PROJECT_ROOT}/api/proto/*/v1/"

