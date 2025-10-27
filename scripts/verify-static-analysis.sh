#!/usr/bin/env bash
# 验证静态分析工具集成
# 确保所有工具和配置正确安装

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}静态分析工具集成验证${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 检查函数
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        return 1
    fi
}

ERRORS=0

# 1. 检查配置文件
echo -e "${YELLOW}[1/6] 检查配置文件...${NC}"
echo ""

if [ -f ".golangci.yml" ]; then
    check ".golangci.yml 存在"
else
    check ".golangci.yml 缺失"
    ((ERRORS++))
fi

if [ -f "pyproject.toml" ]; then
    check "pyproject.toml 存在"
    if grep -q "ARG" pyproject.toml; then
        check "pyproject.toml 包含 ARG 规则"
    else
        check "pyproject.toml 缺少 ARG 规则"
        ((ERRORS++))
    fi
else
    check "pyproject.toml 缺失"
    ((ERRORS++))
fi

echo ""

# 2. 检查 CI/CD 配置
echo -e "${YELLOW}[2/6] 检查 CI/CD 配置...${NC}"
echo ""

if [ -f ".github/workflows/unused-code-check.yml" ]; then
    check "CI workflow 存在"
else
    check "CI workflow 缺失"
    ((ERRORS++))
fi

echo ""

# 3. 检查脚本
echo -e "${YELLOW}[3/6] 检查脚本...${NC}"
echo ""

if [ -f "scripts/check-unused-code.sh" ] && [ -x "scripts/check-unused-code.sh" ]; then
    check "check-unused-code.sh 存在且可执行"
else
    check "check-unused-code.sh 缺失或不可执行"
    ((ERRORS++))
fi

if [ -f "scripts/analyze-unused-code.py" ] && [ -x "scripts/analyze-unused-code.py" ]; then
    check "analyze-unused-code.py 存在且可执行"
else
    check "analyze-unused-code.py 缺失或不可执行"
    ((ERRORS++))
fi

echo ""

# 4. 检查文档
echo -e "${YELLOW}[4/6] 检查文档...${NC}"
echo ""

DOCS=(
    "docs/code-quality/README.md"
    "docs/code-quality/UNUSED_CODE_DETECTION.md"
    "docs/code-quality/QUICKSTART.md"
    "STATIC_ANALYSIS_INTEGRATION.md"
    "CODE_REVIEW_UNUSED_FUNCTIONS.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check "$doc 存在"
    else
        check "$doc 缺失"
        ((ERRORS++))
    fi
done

echo ""

# 5. 检查工具安装
echo -e "${YELLOW}[5/6] 检查工具安装...${NC}"
echo ""

if command -v golangci-lint &> /dev/null; then
    VERSION=$(golangci-lint version 2>&1 | head -1)
    check "golangci-lint 已安装 ($VERSION)"
else
    check "golangci-lint 未安装"
    echo -e "   ${YELLOW}安装: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest${NC}"
    ((ERRORS++))
fi

if command -v ruff &> /dev/null; then
    VERSION=$(ruff --version 2>&1)
    check "ruff 已安装 ($VERSION)"
else
    check "ruff 未安装"
    echo -e "   ${YELLOW}安装: pip install ruff${NC}"
    ((ERRORS++))
fi

if command -v vulture &> /dev/null; then
    check "vulture 已安装"
else
    check "vulture 未安装"
    echo -e "   ${YELLOW}安装: pip install vulture${NC}"
    ((ERRORS++))
fi

echo ""

# 6. 检查 Makefile 目标
echo -e "${YELLOW}[6/6] 检查 Makefile 目标...${NC}"
echo ""

TARGETS=("lint-go" "lint-python" "check-unused" "check-unused-fix" "analyze-unused")

for target in "${TARGETS[@]}"; do
    if grep -q "^$target:" Makefile 2>/dev/null; then
        check "Make target '$target' 存在"
    else
        check "Make target '$target' 缺失"
        ((ERRORS++))
    fi
done

echo ""
echo -e "${BLUE}================================${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ 验证通过！所有组件已正确安装${NC}"
    echo ""
    echo "下一步:"
    echo "  1. 运行检测: make check-unused"
    echo "  2. 查看指南: cat docs/code-quality/QUICKSTART.md"
    echo "  3. 生成报告: make analyze-unused"
    exit 0
else
    echo -e "${RED}✗ 验证失败：发现 $ERRORS 个问题${NC}"
    echo ""
    echo "请修复上述问题后重新运行验证"
    exit 1
fi
