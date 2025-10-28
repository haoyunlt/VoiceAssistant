#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper 服务测试脚本
# 用途: 执行服务的单元测试、集成测试

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 测试统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查测试依赖..."

    if ! command -v go &> /dev/null; then
        log_fail "Go 未安装"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_fail "Python3 未安装"
        exit 1
    fi

    log_success "测试依赖检查完成"
}

# 测试 Go 服务
test_go_services() {
    log_info "测试 Go 服务..."
    echo ""

    local services=(
        "identity-service"
        "conversation-service"
        "knowledge-service"
        "ai-orchestrator"
        "model-router"
        "notification-service"
        "analytics-service"
    )

    for service in "${services[@]}"; do
        local service_dir="${PROJECT_ROOT}/cmd/${service}"

        if [ ! -d "$service_dir" ]; then
            log_warn "$service 目录不存在，跳过"
            continue
        fi

        log_info "测试 $service..."
        TOTAL_TESTS=$((TOTAL_TESTS + 1))

        cd "$service_dir"

        if go test -v ./... 2>&1 | tee "/tmp/${service}-test.log"; then
            log_success "$service 测试通过"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log_fail "$service 测试失败"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            log_warn "查看日志: /tmp/${service}-test.log"
        fi

        echo ""
    done

    cd "$PROJECT_ROOT"
}

# 测试 Python 服务
test_python_services() {
    log_info "测试 Python AI 服务..."
    echo ""

    local services=(
        "agent-engine"
        "rag-engine"
        "voice-engine"
        "model-adapter"
        "retrieval-service"
        "indexing-service"
        "multimodal-engine"
        "vector-store-adapter"
        "knowledge-service"
    )

    for service in "${services[@]}"; do
        local service_dir="${PROJECT_ROOT}/algo/${service}"

        if [ ! -d "$service_dir" ]; then
            log_warn "$service 目录不存在，跳过"
            continue
        fi

        # 检查是否有测试文件
        if [ ! -d "$service_dir/tests" ] && [ ! -f "$service_dir/test_*.py" ]; then
            log_warn "$service 没有测试文件，跳过"
            continue
        fi

        log_info "测试 $service..."
        TOTAL_TESTS=$((TOTAL_TESTS + 1))

        cd "$service_dir"

        # 激活虚拟环境（如果存在）
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi

        # 检查 pytest 是否可用
        if ! python3 -c "import pytest" 2>/dev/null; then
            log_warn "$service: pytest 未安装，跳过"
            continue
        fi

        if pytest tests/ -v 2>&1 | tee "/tmp/${service}-test.log"; then
            log_success "$service 测试通过"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log_fail "$service 测试失败"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            log_warn "查看日志: /tmp/${service}-test.log"
        fi

        # 退出虚拟环境
        if [ -f "venv/bin/activate" ]; then
            deactivate 2>/dev/null || true
        fi

        echo ""
    done

    cd "$PROJECT_ROOT"
}

# 测试共享包
test_shared_packages() {
    log_info "测试共享包..."
    echo ""

    # Go 共享包
    log_info "测试 Go pkg..."
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    cd "${PROJECT_ROOT}"

    if go test ./pkg/... -v 2>&1 | tee "/tmp/pkg-test.log"; then
        log_success "Go pkg 测试通过"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        log_fail "Go pkg 测试失败"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    echo ""

    # Python 共享包
    if [ -d "${PROJECT_ROOT}/algo/common/tests" ]; then
        log_info "测试 Python common..."
        TOTAL_TESTS=$((TOTAL_TESTS + 1))

        cd "${PROJECT_ROOT}/algo/common"

        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi

        if pytest tests/ -v 2>&1 | tee "/tmp/common-test.log"; then
            log_success "Python common 测试通过"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            log_fail "Python common 测试失败"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi

        if [ -f "venv/bin/activate" ]; then
            deactivate 2>/dev/null || true
        fi

        echo ""
    fi
}

# 运行代码覆盖率测试
test_with_coverage() {
    log_info "运行覆盖率测试..."
    echo ""

    # Go 覆盖率
    log_info "Go 服务覆盖率..."
    cd "${PROJECT_ROOT}"

    go test -coverprofile=coverage.out ./... 2>&1 | tee "/tmp/go-coverage.log"

    if [ -f coverage.out ]; then
        local go_coverage=$(go tool cover -func=coverage.out | grep total | awk '{print $3}')
        log_info "Go 总体覆盖率: $go_coverage"

        # 生成 HTML 报告
        go tool cover -html=coverage.out -o coverage.html
        log_success "Go 覆盖率报告: coverage.html"
    fi

    echo ""
}

# 运行 lint 检查
run_linters() {
    log_info "运行代码检查..."
    echo ""

    # Go lint
    if command -v golangci-lint &> /dev/null; then
        log_info "Go 代码检查..."
        cd "${PROJECT_ROOT}/cmd"

        if golangci-lint run ./... 2>&1 | tee "/tmp/golangci-lint.log"; then
            log_success "Go 代码检查通过"
        else
            log_warn "Go 代码存在问题，查看: /tmp/golangci-lint.log"
        fi
    else
        log_warn "golangci-lint 未安装，跳过 Go 代码检查"
    fi

    echo ""

    # Python lint
    if command -v ruff &> /dev/null; then
        log_info "Python 代码检查..."
        cd "${PROJECT_ROOT}/algo"

        if ruff check . 2>&1 | tee "/tmp/ruff-check.log"; then
            log_success "Python 代码检查通过"
        else
            log_warn "Python 代码存在问题，查看: /tmp/ruff-check.log"
        fi
    else
        log_warn "ruff 未安装，跳过 Python 代码检查"
    fi

    echo ""
}

# 生成测试报告
generate_report() {
    echo ""
    log_info "========================================"
    log_info "测试报告"
    log_info "========================================"
    echo ""

    if [ "$TOTAL_TESTS" -eq 0 ]; then
        log_warn "未执行任何测试"
        return 1
    fi

    echo "总测试套件: $TOTAL_TESTS"
    echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
    echo -e "${RED}失败: $FAILED_TESTS${NC}"
    echo ""

    local success_rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS/$TOTAL_TESTS)*100}")
    echo "成功率: ${success_rate}%"
    echo ""

    log_info "测试日志保存在: /tmp/*-test.log"

    if [ "$FAILED_TESTS" -eq 0 ]; then
        log_success "所有测试通过！"
        return 0
    else
        log_fail "$FAILED_TESTS 个测试套件失败"
        return 1
    fi
}

# 显示帮助
show_help() {
    cat << EOF
VoiceHelper 服务测试脚本

用法: $0 [选项]

选项:
  --go-only        仅测试 Go 服务
  --python-only    仅测试 Python 服务
  --coverage       运行覆盖率测试
  --lint           运行代码检查
  --all            运行所有测试（默认）
  -h, --help       显示帮助信息

示例:
  $0                  # 运行所有测试
  $0 --go-only        # 仅测试 Go 服务
  $0 --coverage       # 运行覆盖率测试
  $0 --lint           # 运行代码检查

EOF
}

# 主函数
main() {
    local test_go=true
    local test_python=true
    local run_coverage=false
    local run_lint=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --go-only)
                test_python=false
                shift
                ;;
            --python-only)
                test_go=false
                shift
                ;;
            --coverage)
                run_coverage=true
                shift
                ;;
            --lint)
                run_lint=true
                shift
                ;;
            --all)
                # 默认行为
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_fail "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo ""
    log_info "========================================"
    log_info "VoiceHelper 服务测试"
    log_info "========================================"
    echo ""

    check_dependencies
    echo ""

    if [ "$run_lint" = true ]; then
        run_linters
    fi

    if [ "$test_go" = true ]; then
        test_go_services
    fi

    if [ "$test_python" = true ]; then
        test_python_services
    fi

    test_shared_packages

    if [ "$run_coverage" = true ]; then
        test_with_coverage
    fi

    generate_report
}

# 执行主函数
main "$@"
