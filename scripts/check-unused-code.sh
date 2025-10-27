#!/bin/bash
# 本地未使用代码检测脚本
# 使用方法: ./scripts/check-unused-code.sh [--fix]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 解析参数
FIX_MODE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            echo "使用方法: $0 [--fix] [--verbose]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}未使用代码检测工具${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 检查工具是否安装
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ $1 未安装${NC}"
        echo "   安装: $2"
        return 1
    fi
    echo -e "${GREEN}✓${NC} $1"
    return 0
}

echo "检查必要工具..."
TOOLS_OK=true

check_tool "golangci-lint" "go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest" || TOOLS_OK=false
check_tool "ruff" "pip install ruff" || TOOLS_OK=false
check_tool "vulture" "pip install vulture" || TOOLS_OK=false

echo ""

if [ "$TOOLS_OK" = false ]; then
    echo -e "${RED}请先安装缺失的工具${NC}"
    exit 1
fi

# 创建报告目录
REPORT_DIR="$PROJECT_ROOT/.reports"
mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
GO_REPORT="$REPORT_DIR/unused-go-$TIMESTAMP.txt"
PY_REPORT="$REPORT_DIR/unused-python-$TIMESTAMP.txt"
SUMMARY_REPORT="$REPORT_DIR/unused-summary-$TIMESTAMP.md"

# 分析 Go 代码
echo -e "${BLUE}🔍 分析 Go 代码...${NC}"
echo ""

GO_ARGS="--enable=unused,deadcode,unparam,ineffassign,varcheck,structcheck --timeout=5m"

if [ "$FIX_MODE" = true ]; then
    echo -e "${YELLOW}自动修复模式（仅限安全修复）${NC}"
    golangci-lint run $GO_ARGS --fix ./... 2>&1 | tee "$GO_REPORT"
else
    golangci-lint run $GO_ARGS ./... 2>&1 | tee "$GO_REPORT"
fi

GO_ISSUES=$(grep -c ":" "$GO_REPORT" 2>/dev/null || echo "0")

if [ "$GO_ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✅ Go 代码：未发现未使用代码${NC}"
else
    echo -e "${YELLOW}⚠️  Go 代码：发现 $GO_ISSUES 个问题${NC}"
fi

echo ""

# 分析 Python 代码
echo -e "${BLUE}🔍 分析 Python 代码...${NC}"
echo ""

# Ruff 检查
echo "运行 Ruff 检查..."
if [ "$FIX_MODE" = true ]; then
    ruff check algo/ --select F401,F841,ARG --fix 2>&1 | tee "$PY_REPORT"
else
    ruff check algo/ --select F401,F841,ARG 2>&1 | tee "$PY_REPORT"
fi

# Vulture 检查
echo ""
echo "运行 Vulture 死代码检测..."
vulture algo/ --min-confidence 80 --sort-by-size 2>&1 | tee -a "$PY_REPORT"

PY_ISSUES=$(grep -c ":" "$PY_REPORT" 2>/dev/null || echo "0")

if [ "$PY_ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✅ Python 代码：未发现未使用代码${NC}"
else
    echo -e "${YELLOW}⚠️  Python 代码：发现 $PY_ISSUES 个问题${NC}"
fi

echo ""

# 生成摘要报告
echo -e "${BLUE}📊 生成摘要报告...${NC}"

cat > "$SUMMARY_REPORT" << EOF
# 未使用代码检测报告

> 生成时间: $(date)
> 报告位置: $REPORT_DIR

## 摘要

- **Go 代码问题**: $GO_ISSUES 个
- **Python 代码问题**: $PY_ISSUES 个
- **总计**: $((GO_ISSUES + PY_ISSUES)) 个

## Go 代码

详细报告: $GO_REPORT

\`\`\`
$(head -n 20 "$GO_REPORT")
$([ "$(wc -l < "$GO_REPORT")" -gt 20 ] && echo "... (查看完整报告)")
\`\`\`

## Python 代码

详细报告: $PY_REPORT

\`\`\`
$(head -n 20 "$PY_REPORT")
$([ "$(wc -l < "$PY_REPORT")" -gt 20 ] && echo "... (查看完整报告)")
\`\`\`

## 建议

1. 检查报告中的问题
2. 确认是否为死代码或预留功能
3. 删除不需要的代码
4. 更新文档说明预留代码

## 命令

手动检查特定目录:

\`\`\`bash
# Go
golangci-lint run --enable=unused cmd/service-name/...

# Python
ruff check algo/service-name/ --select F401,F841,ARG
vulture algo/service-name/ --min-confidence 80
\`\`\`
EOF

echo -e "${GREEN}✅ 报告已生成: $SUMMARY_REPORT${NC}"
echo ""

# 显示摘要
cat "$SUMMARY_REPORT"

# 退出码
TOTAL_ISSUES=$((GO_ISSUES + PY_ISSUES))

if [ $TOTAL_ISSUES -eq 0 ]; then
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}✅ 检测完成：未发现问题${NC}"
    echo -e "${GREEN}================================${NC}"
    exit 0
else
    echo ""
    echo -e "${YELLOW}================================${NC}"
    echo -e "${YELLOW}⚠️  检测完成：发现 $TOTAL_ISSUES 个问题${NC}"
    echo -e "${YELLOW}================================${NC}"
    echo ""
    echo "查看详细报告:"
    echo "  - Go:     $GO_REPORT"
    echo "  - Python: $PY_REPORT"
    echo "  - 摘要:   $SUMMARY_REPORT"

    if [ "$FIX_MODE" = false ]; then
        echo ""
        echo "使用 --fix 选项尝试自动修复安全问题:"
        echo "  ./scripts/check-unused-code.sh --fix"
    fi

    exit 1
fi
