#!/usr/bin/env bash

set -euo pipefail

# Build script for VoiceAssistant services
# Usage: ./scripts/build.sh [go|python|frontend|all]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_TYPE="${1:-all}"

echo "==> Building VoiceAssistant services (type: ${BUILD_TYPE})"

# Build Go services
build_go() {
    echo "==> Building Go services..."
    
    GO_SERVICES=(
        "identity-service"
        "conversation-service"
        "knowledge-service"
        "ai-orchestrator"
        "model-router"
        "notification-service"
        "analytics-service"
    )
    
    for service in "${GO_SERVICES[@]}"; do
        echo "  -> Building ${service}..."
        docker build \
            -f "${PROJECT_ROOT}/deployments/docker/Dockerfile.go-service" \
            -t "voiceassistant/${service}:latest" \
            --build-arg SERVICE_NAME="${service}" \
            "${PROJECT_ROOT}"
    done
    
    echo "✓ Go services built successfully"
}

# Build Python services
build_python() {
    echo "==> Building Python services..."
    
    PYTHON_SERVICES=(
        "agent-engine"
        "rag-engine"
        "indexing-service"
        "retrieval-service"
        "voice-engine"
        "multimodal-engine"
        "model-adapter"
    )
    
    for service in "${PYTHON_SERVICES[@]}"; do
        echo "  -> Building ${service}..."
        docker build \
            -f "${PROJECT_ROOT}/deployments/docker/Dockerfile.python-service" \
            -t "voiceassistant/${service}:latest" \
            --build-arg SERVICE_NAME="${service}" \
            "${PROJECT_ROOT}"
    done
    
    echo "✓ Python services built successfully"
}

# Build Frontend
build_frontend() {
    echo "==> Building Frontend..."
    
    # Build Web
    echo "  -> Building web platform..."
    docker build \
        -f "${PROJECT_ROOT}/platforms/web/Dockerfile" \
        -t "voiceassistant/web:latest" \
        "${PROJECT_ROOT}/platforms/web"
    
    # Build Admin
    echo "  -> Building admin platform..."
    docker build \
        -f "${PROJECT_ROOT}/platforms/admin/Dockerfile" \
        -t "voiceassistant/admin:latest" \
        "${PROJECT_ROOT}/platforms/admin"
    
    echo "✓ Frontend built successfully"
}

case "${BUILD_TYPE}" in
    go)
        build_go
        ;;
    python)
        build_python
        ;;
    frontend)
        build_frontend
        ;;
    all)
        build_go
        build_python
        build_frontend
        ;;
    *)
        echo "Error: Unknown build type: ${BUILD_TYPE}"
        echo "Usage: $0 [go|python|frontend|all]"
        exit 1
        ;;
esac

echo ""
echo "==> Build completed successfully!"

