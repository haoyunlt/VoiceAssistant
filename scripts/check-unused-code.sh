#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper 未使用代码检测脚本
# 用途: 检测 Go 和 Python 代码中的未使用函数、变量和导入

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORT_DIR="${PROJECT_ROOT}/.reports"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 统计
GO_UNUSED_FUNCTIONS=0
PY_UNUSED_FUNCTIONS=0
AUTO_FIX=false

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

# 创建报告目录
setup_report_dir() {
    mkdir -p "$REPORT_DIR"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    REPORT_FILE="${REPORT_DIR}/unused-summary-${timestamp}.md"
}

# 检查 Go 工具
check_go_tools() {
    log_info "检查 Go 工具..."

    if ! command -v go &> /dev/null; then
        log_fail "Go 未安装"
        return 1
    fi

    # 检查 staticcheck
    if ! command -v staticcheck &> /dev/null; then
        log_warn "staticcheck 未安装，尝试安装..."
        go install honnef.co/go/tools/cmd/staticcheck@latest
    fi

    # 检查 golangci-lint
    if ! command -v golangci-lint &> /dev/null; then
        log_warn "golangci-lint 未安装，跳过 lint 检查"
    fi

    log_success "Go 工具检查完成"
}

# 检查 Python 工具
check_python_tools() {
    log_info "检查 Python 工具..."

    if ! command -v python3 &> /dev/null; then
        log_fail "Python3 未安装"
        return 1
    fi

    # 检查 vulture
    if ! command -v vulture &> /dev/null; then
        log_warn "vulture 未安装，尝试安装..."
        pip3 install vulture
    fi

    # 检查 ruff
    if ! command -v ruff &> /dev/null; then
        log_warn "ruff 未安装"
    fi

    log_success "Python 工具检查完成"
}

# 检测 Go 未使用代码
check_go_unused() {
    log_info "检测 Go 未使用代码..."

    cd "$PROJECT_ROOT"

    local go_report="${REPORT_DIR}/go-unused.txt"

    # 使用 staticcheck 检测
    if command -v staticcheck &> /dev/null; then
        log_info "使用 staticcheck 分析..."
        staticcheck ./cmd/... ./pkg/... ./internal/... 2>&1 | grep -E "(unused|U1000)" > "$go_report" || true

        GO_UNUSED_FUNCTIONS=$(wc -l < "$go_report" | tr -d ' ')

        if [ "$GO_UNUSED_FUNCTIONS" -gt 0 ]; then
            log_warn "发现 $GO_UNUSED_FUNCTIONS 个 Go 未使用项"
            echo ""
            echo "前 10 个未使用项:"
            head -10 "$go_report"
            echo ""
        else
            log_success "未发现 Go 未使用代码"
        fi
    fi

    # 使用 golangci-lint 检测
    if command -v golangci-lint &> /dev/null; then
        log_info "使用 golangci-lint 分析..."
        golangci-lint run --disable-all --enable=unused,deadcode,structcheck,varcheck ./cmd/... ./pkg/... 2>&1 | \
            tee "${REPORT_DIR}/golangci-unused.txt" || true
    fi
}

# 检测 Python 未使用代码
check_python_unused() {
    log_info "检测 Python 未使用代码..."

    cd "$PROJECT_ROOT/algo"

    local py_report="${REPORT_DIR}/python-unused.txt"

    # 使用 vulture 检测
    if command -v vulture &> /dev/null; then
        log_info "使用 vulture 分析..."

        vulture . --min-confidence 80 --exclude "venv,__pycache__,.pytest_cache" > "$py_report" 2>&1 || true

        PY_UNUSED_FUNCTIONS=$(grep -c "unused function" "$py_report" 2>/dev/null || echo "0")

        if [ "$PY_UNUSED_FUNCTIONS" -gt 0 ]; then
            log_warn "发现 $PY_UNUSED_FUNCTIONS 个 Python 未使用函数"
            echo ""
            echo "前 10 个未使用函数:"
            grep "unused function" "$py_report" | head -10
            echo ""
        else
            log_success "未发现 Python 未使用代码"
        fi
    fi

    # 使用 ruff 检测未使用导入
    if command -v ruff &> /dev/null; then
        log_info "使用 ruff 检测未使用导入..."
        ruff check --select F401,F841 . 2>&1 | tee "${REPORT_DIR}/ruff-unused.txt" || true
    fi
}

# 自动修复 Go 未使用导入
fix_go_unused_imports() {
    if [ "$AUTO_FIX" != "true" ]; then
        return 0
    fi

    log_info "自动修复 Go 未使用导入..."

    cd "$PROJECT_ROOT"

    # 使用 goimports 修复
    if command -v goimports &> /dev/null; then
        find ./cmd ./pkg ./internal -name "*.go" -exec goimports -w {} \;
        log_success "Go 未使用导入已修复"
    else
        log_warn "goimports 未安装，跳过自动修复"
    fi
}

# 自动修复 Python 未使用导入
fix_python_unused_imports() {
    if [ "$AUTO_FIX" != "true" ]; then
        return 0
    fi

    log_info "自动修复 Python 未使用导入..."

    cd "$PROJECT_ROOT/algo"

    # 使用 ruff 修复
    if command -v ruff &> /dev/null; then
        ruff check --select F401 --fix .
        log_success "Python 未使用导入已修复"
    else
        log_warn "ruff 未安装，跳过自动修复"
    fi
}

# 生成 Markdown 报告
generate_report() {
    log_info "生成报告..."

    cat > "$REPORT_FILE" << EOF
# VoiceHelper 未使用代码检测报告

**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')

## 摘要

- **Go 未使用项**: $GO_UNUSED_FUNCTIONS
- **Python 未使用函数**: $PY_UNUSED_FUNCTIONS
- **总计**: $((GO_UNUSED_FUNCTIONS + PY_UNUSED_FUNCTIONS))

## Go 未使用代码

EOF

    if [ -f "${REPORT_DIR}/go-unused.txt" ] && [ -s "${REPORT_DIR}/go-unused.txt" ]; then
        echo '```' >> "$REPORT_FILE"
        cat "${REPORT_DIR}/go-unused.txt" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
    else
        echo "未发现 Go 未使用代码" >> "$REPORT_FILE"
    fi

    cat >> "$REPORT_FILE" << EOF

## Python 未使用代码

EOF

    if [ -f "${REPORT_DIR}/python-unused.txt" ] && [ -s "${REPORT_DIR}/python-unused.txt" ]; then
        echo '```' >> "$REPORT_FILE"
        head -50 "${REPORT_DIR}/python-unused.txt" >> "$REPORT_FILE"
        echo '```' >> "$REPORT_FILE"
    else
        echo "未发现 Python 未使用代码" >> "$REPORT_FILE"
    fi

    cat >> "$REPORT_FILE" << EOF

## 建议

1. 审查上述未使用代码，确认是否可以删除
2. 如果是测试辅助函数或将来使用，添加注释说明
3. 定期运行此检查，保持代码整洁

## 详细报告

- Go 详细报告: \`.reports/go-unused.txt\`
- Python 详细报告: \`.reports/python-unused.txt\`

EOF

    log_success "报告已生成: $REPORT_FILE"
}

# 显示摘要
show_summary() {
    echo ""
    log_info "========================================"
    log_info "未使用代码检测完成"
    log_info "========================================"
    echo ""
    echo "Go 未使用项: $GO_UNUSED_FUNCTIONS"
    echo "Python 未使用函数: $PY_UNUSED_FUNCTIONS"
    echo "总计: $((GO_UNUSED_FUNCTIONS + PY_UNUSED_FUNCTIONS))"
    echo ""
    log_info "详细报告: $REPORT_FILE"
    echo ""

    if [ "$AUTO_FIX" = "true" ]; then
        log_success "已自动修复未使用的导入"
    else
        log_info "运行 '$0 --fix' 自动修复未使用的导入"
    fi
    echo ""
}

# 显示帮助
show_help() {
    cat << EOF
VoiceHelper 未使用代码检测脚本

用法: $0 [选项]

选项:
  --fix              自动修复未使用的导入
  --go-only          仅检测 Go 代码
  --python-only      仅检测 Python 代码
  -h, --help         显示帮助信息

示例:
  $0                 # 检测所有代码
  $0 --fix           # 检测并自动修复
  $0 --go-only       # 仅检测 Go 代码

工具要求:
  Go:     staticcheck, golangci-lint (可选)
  Python: vulture, ruff

报告目录: .reports/

EOF
}

# 主函数
main() {
    local check_go=true
    local check_python=true

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --fix)
                AUTO_FIX=true
                shift
                ;;
            --go-only)
                check_python=false
                shift
                ;;
            --python-only)
                check_go=false
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
    log_info "未使用代码检测"
    log_info "========================================"
    echo ""

    setup_report_dir

    if [ "$check_go" = "true" ]; then
        check_go_tools
        echo ""
        check_go_unused
        echo ""
        fix_go_unused_imports
        echo ""
    fi

    if [ "$check_python" = "true" ]; then
        check_python_tools
        echo ""
        check_python_unused
        echo ""
        fix_python_unused_imports
        echo ""
    fi

    generate_report
    show_summary
}

# 执行主函数
main "$@"
