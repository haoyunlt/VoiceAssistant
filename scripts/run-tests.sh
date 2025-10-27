#!/bin/bash
# 运行改进后的单元测试
# 用法: ./scripts/run-tests.sh [service_name]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Python 是否安装
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_info "Python version: $(python3 --version)"
}

# 检查 pytest 是否安装
check_pytest() {
    if ! python3 -c "import pytest" 2> /dev/null; then
        log_warn "pytest not found, installing..."
        pip install pytest pytest-asyncio pytest-cov pytest-mock
    fi
}

# 运行特定服务的测试
run_service_tests() {
    local service=$1
    local service_path="algo/${service}"

    if [ ! -d "$service_path" ]; then
        log_error "Service directory not found: $service_path"
        return 1
    fi

    log_info "Running tests for ${service}..."

    cd "$service_path"

    # 安装依赖（如果需要）
    if [ -f "requirements.txt" ]; then
        log_info "Installing dependencies..."
        pip install -q -r requirements.txt
    fi

    # 运行测试
    if [ -d "tests" ]; then
        log_info "Running pytest..."
        PYTHONPATH="../../:$PYTHONPATH" pytest tests/ -v --tb=short
        test_result=$?

        if [ $test_result -eq 0 ]; then
            log_info "✅ Tests passed for ${service}"
        else
            log_error "❌ Tests failed for ${service}"
            return $test_result
        fi
    else
        log_warn "No tests directory found for ${service}"
    fi

    cd - > /dev/null
}

# 运行所有测试
run_all_tests() {
    log_info "Running all tests..."

    local services=(
        "agent-engine"
        "retrieval-service"
        "model-adapter"
        "rag-engine"
        "voice-engine"
        "indexing-service"
    )

    local failed_services=()

    for service in "${services[@]}"; do
        if run_service_tests "$service"; then
            log_info "✅ ${service} tests passed"
        else
            log_error "❌ ${service} tests failed"
            failed_services+=("$service")
        fi
        echo ""
    done

    # 总结
    echo "======================================"
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_info "🎉 All tests passed!"
        return 0
    else
        log_error "Some tests failed:"
        for service in "${failed_services[@]}"; do
            echo "  - $service"
        done
        return 1
    fi
}

# 运行通用测试（algo/common）
run_common_tests() {
    log_info "Running common module tests..."

    cd algo/common

    if [ -d "tests" ]; then
        log_info "Running pytest for common module..."
        PYTHONPATH="../..:$PYTHONPATH" pytest tests/ -v --tb=short
        test_result=$?

        if [ $test_result -eq 0 ]; then
            log_info "✅ Common tests passed"
        else
            log_error "❌ Common tests failed"
            return $test_result
        fi
    else
        log_warn "No tests directory found for common module"
    fi

    cd - > /dev/null
}

# 生成覆盖率报告
generate_coverage() {
    log_info "Generating coverage report..."

    local service=$1
    local service_path="algo/${service}"

    if [ ! -d "$service_path" ]; then
        log_error "Service directory not found: $service_path"
        return 1
    fi

    cd "$service_path"

    if [ -d "tests" ]; then
        log_info "Running pytest with coverage..."
        PYTHONPATH="../../:$PYTHONPATH" pytest tests/ --cov=app --cov-report=html --cov-report=term

        log_info "Coverage report generated: ${service_path}/htmlcov/index.html"

        # 尝试打开浏览器
        if command -v open &> /dev/null; then
            open htmlcov/index.html
        elif command -v xdg-open &> /dev/null; then
            xdg-open htmlcov/index.html
        fi
    fi

    cd - > /dev/null
}

# 主函数
main() {
    log_info "Starting test runner..."

    check_python
    check_pytest

    # 获取命令行参数
    local command=${1:-all}
    local service=${2:-}

    case "$command" in
        all)
            run_all_tests
            ;;
        common)
            run_common_tests
            ;;
        service)
            if [ -z "$service" ]; then
                log_error "Service name required. Usage: $0 service <service-name>"
                exit 1
            fi
            run_service_tests "$service"
            ;;
        coverage)
            if [ -z "$service" ]; then
                log_error "Service name required. Usage: $0 coverage <service-name>"
                exit 1
            fi
            generate_coverage "$service"
            ;;
        help)
            echo "Usage: $0 [command] [options]"
            echo ""
            echo "Commands:"
            echo "  all               Run all service tests (default)"
            echo "  common            Run common module tests"
            echo "  service <name>    Run specific service tests"
            echo "  coverage <name>   Generate coverage report for service"
            echo "  help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 all"
            echo "  $0 service agent-engine"
            echo "  $0 coverage agent-engine"
            ;;
        *)
            log_error "Unknown command: $command"
            log_info "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
