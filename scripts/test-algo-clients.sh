#!/bin/bash

# 算法服务客户端测试脚本
# 用于快速测试所有算法服务的连接性和基本功能

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# 检查服务是否运行
check_service() {
    local service_name=$1
    local service_url=$2

    print_info "Checking $service_name at $service_url..."

    if curl -s -f "$service_url/health" > /dev/null 2>&1; then
        print_success "$service_name is running"
        return 0
    else
        print_warning "$service_name is not accessible"
        return 1
    fi
}

# 主函数
main() {
    print_header "算法服务客户端测试"

    # 设置默认服务URL（如果未设置）
    export AGENT_ENGINE_URL=${AGENT_ENGINE_URL:-"http://localhost:8010"}
    export RAG_ENGINE_URL=${RAG_ENGINE_URL:-"http://localhost:8006"}
    export RETRIEVAL_SERVICE_URL=${RETRIEVAL_SERVICE_URL:-"http://localhost:8012"}
    export MODEL_ADAPTER_URL=${MODEL_ADAPTER_URL:-"http://localhost:8005"}
    export VOICE_ENGINE_URL=${VOICE_ENGINE_URL:-"http://localhost:8004"}
    export MULTIMODAL_ENGINE_URL=${MULTIMODAL_ENGINE_URL:-"http://localhost:8007"}
    export INDEXING_SERVICE_URL=${INDEXING_SERVICE_URL:-"http://localhost:8000"}
    export VECTOR_STORE_ADAPTER_URL=${VECTOR_STORE_ADAPTER_URL:-"http://localhost:8009"}

    print_header "1. 检查服务可用性"

    # 检查所有服务
    services=(
        "Agent Engine:$AGENT_ENGINE_URL"
        "RAG Engine:$RAG_ENGINE_URL"
        "Retrieval Service:$RETRIEVAL_SERVICE_URL"
        "Model Adapter:$MODEL_ADAPTER_URL"
        "Voice Engine:$VOICE_ENGINE_URL"
        "Multimodal Engine:$MULTIMODAL_ENGINE_URL"
        "Indexing Service:$INDEXING_SERVICE_URL"
        "Vector Store Adapter:$VECTOR_STORE_ADAPTER_URL"
    )

    healthy_count=0
    total_count=${#services[@]}

    for service in "${services[@]}"; do
        IFS=':' read -r name url <<< "$service"
        if check_service "$name" "$url"; then
            ((healthy_count++))
        fi
    done

    echo ""
    print_info "Summary: $healthy_count/$total_count services are healthy"

    # 如果没有服务在运行，给出提示
    if [ $healthy_count -eq 0 ]; then
        print_error "No services are running!"
        echo ""
        print_info "Please start the services first:"
        echo "  - Agent Engine: cd algo/agent-engine && python main.py"
        echo "  - RAG Engine: cd algo/rag-engine && python main.py"
        echo "  - Voice Engine: cd algo/voice-engine && python main.py"
        echo "  - Multimodal Engine: cd algo/multimodal-engine && python main.py"
        echo "  - Indexing Service: cd algo/indexing-service && python main.py"
        echo "  - Vector Store Adapter: cd algo/vector-store-adapter && python main_refactored.py"
        echo "  - Retrieval Service: cd algo/retrieval-service && python main.py"
        echo "  - Model Adapter: cd algo/model-adapter && python main_refactored.py"
        echo ""
        exit 1
    fi

    # 运行Go集成测试
    print_header "2. 运行Go集成测试"

    if [ -f "tests/integration/algo_clients_integration_test.go" ]; then
        print_info "Running integration tests..."
        if go test -v -timeout 2m ./tests/integration/algo_clients_integration_test.go; then
            print_success "Integration tests passed"
        else
            print_error "Integration tests failed"
        fi
    else
        print_warning "Integration test file not found"
    fi

    # 运行示例程序
    print_header "3. 运行示例程序"

    if [ -f "examples/algo_client_example.go" ]; then
        print_info "Running example program..."
        if go run examples/algo_client_example.go; then
            print_success "Example program completed"
        else
            print_error "Example program failed"
        fi
    else
        print_warning "Example program not found"
    fi

    # 总结
    print_header "测试完成"

    if [ $healthy_count -eq $total_count ]; then
        print_success "All services are healthy and tests passed!"
    elif [ $healthy_count -gt 0 ]; then
        print_warning "Some services are not healthy, but tests completed"
    else
        print_error "No services are healthy"
    fi

    echo ""
    print_info "Next steps:"
    echo "  1. Check service logs if any tests failed"
    echo "  2. Review the integration guide: docs/algo-api-integration.md"
    echo "  3. Read the client documentation: pkg/clients/algo/README.md"
    echo ""
}

# 运行主函数
main "$@"

