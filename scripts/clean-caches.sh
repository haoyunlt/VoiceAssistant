#!/bin/bash
# 清理项目缓存以优化 Cursor 性能

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧹 清理项目缓存"
echo "================================"
echo ""
echo "📁 项目路径: $PROJECT_ROOT"
echo ""

# 统计清理前的文件数
BEFORE_COUNT=$(find . -type f -not -path "*/.git/*" 2>/dev/null | wc -l | tr -d ' ')
echo "清理前文件数: $BEFORE_COUNT"
echo ""

# 清理计数
CLEANED_COUNT=0

# 1. Python 缓存
echo "1️⃣  清理 Python 缓存"
echo "--------------------------------"

# __pycache__
PYCACHE_DIRS=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYCACHE_DIRS" -gt 0 ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $PYCACHE_DIRS 个 __pycache__ 目录"
    CLEANED_COUNT=$((CLEANED_COUNT + PYCACHE_DIRS))
else
    echo -e "${YELLOW}•${NC} 无 __pycache__ 目录"
fi

# .pyc, .pyo, .pyd
PYC_FILES=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYC_FILES" -gt 0 ]; then
    find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $PYC_FILES 个 .pyc/.pyo/.pyd 文件"
    CLEANED_COUNT=$((CLEANED_COUNT + PYC_FILES))
else
    echo -e "${YELLOW}•${NC} 无 .pyc/.pyo/.pyd 文件"
fi

# .pytest_cache
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo -e "${GREEN}✓${NC} 清理 .pytest_cache"
    CLEANED_COUNT=$((CLEANED_COUNT + 1))
fi

# .mypy_cache
if [ -d ".mypy_cache" ]; then
    MYPY_SIZE=$(du -sh .mypy_cache 2>/dev/null | cut -f1)
    rm -rf .mypy_cache
    echo -e "${GREEN}✓${NC} 清理 .mypy_cache ($MYPY_SIZE)"
    CLEANED_COUNT=$((CLEANED_COUNT + 1))
fi

# .ruff_cache
if [ -d ".ruff_cache" ]; then
    rm -rf .ruff_cache
    echo -e "${GREEN}✓${NC} 清理 .ruff_cache"
    CLEANED_COUNT=$((CLEANED_COUNT + 1))
fi

# .coverage
if [ -f ".coverage" ]; then
    rm -f .coverage
    echo -e "${GREEN}✓${NC} 清理 .coverage"
fi

# htmlcov
if [ -d "htmlcov" ]; then
    rm -rf htmlcov
    echo -e "${GREEN}✓${NC} 清理 htmlcov"
fi

echo ""

# 2. Go 缓存
echo "2️⃣  清理 Go 缓存"
echo "--------------------------------"

# *.test
TEST_FILES=$(find . -type f -name "*.test" 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEST_FILES" -gt 0 ]; then
    find . -type f -name "*.test" -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $TEST_FILES 个 *.test 文件"
    CLEANED_COUNT=$((CLEANED_COUNT + TEST_FILES))
else
    echo -e "${YELLOW}•${NC} 无 *.test 文件"
fi

# coverage files
COV_FILES=$(find . -type f \( -name "*.out" -o -name "*.coverprofile" \) -not -path "*/.git/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$COV_FILES" -gt 0 ]; then
    find . -type f \( -name "*.out" -o -name "*.coverprofile" \) -not -path "*/.git/*" -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $COV_FILES 个覆盖率文件"
    CLEANED_COUNT=$((CLEANED_COUNT + COV_FILES))
else
    echo -e "${YELLOW}•${NC} 无覆盖率文件"
fi

echo ""

# 3. 临时文件
echo "3️⃣  清理临时文件"
echo "--------------------------------"

# .DS_Store (macOS)
DS_FILES=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
if [ "$DS_FILES" -gt 0 ]; then
    find . -name ".DS_Store" -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $DS_FILES 个 .DS_Store 文件"
    CLEANED_COUNT=$((CLEANED_COUNT + DS_FILES))
else
    echo -e "${YELLOW}•${NC} 无 .DS_Store 文件"
fi

# Vim swap files
VIM_FILES=$(find . -type f \( -name "*.swp" -o -name "*.swo" -o -name "*~" \) 2>/dev/null | wc -l | tr -d ' ')
if [ "$VIM_FILES" -gt 0 ]; then
    find . -type f \( -name "*.swp" -o -name "*.swo" -o -name "*~" \) -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $VIM_FILES 个 Vim 临时文件"
    CLEANED_COUNT=$((CLEANED_COUNT + VIM_FILES))
else
    echo -e "${YELLOW}•${NC} 无 Vim 临时文件"
fi

# *.tmp, *.temp
TMP_FILES=$(find . -type f \( -name "*.tmp" -o -name "*.temp" \) 2>/dev/null | wc -l | tr -d ' ')
if [ "$TMP_FILES" -gt 0 ]; then
    find . -type f \( -name "*.tmp" -o -name "*.temp" \) -delete 2>/dev/null || true
    echo -e "${GREEN}✓${NC} 清理 $TMP_FILES 个临时文件"
    CLEANED_COUNT=$((CLEANED_COUNT + TMP_FILES))
else
    echo -e "${YELLOW}•${NC} 无临时文件"
fi

echo ""

# 4. 日志文件
echo "4️⃣  清理日志文件"
echo "--------------------------------"

LOG_FILES=$(find . -type f -name "*.log" -not -path "*/.git/*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOG_FILES" -gt 0 ]; then
    # 显示大于 1MB 的日志文件
    LARGE_LOGS=$(find . -type f -name "*.log" -size +1M -not -path "*/.git/*" 2>/dev/null)
    if [ -n "$LARGE_LOGS" ]; then
        echo "   发现大型日志文件:"
        echo "$LARGE_LOGS" | while read -r log; do
            SIZE=$(du -h "$log" | cut -f1)
            echo "      - $log ($SIZE)"
        done

        echo ""
        read -p "   是否删除所有 .log 文件? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            find . -type f -name "*.log" -not -path "*/.git/*" -delete 2>/dev/null || true
            echo -e "${GREEN}✓${NC} 清理 $LOG_FILES 个日志文件"
            CLEANED_COUNT=$((CLEANED_COUNT + LOG_FILES))
        else
            echo -e "${YELLOW}•${NC} 跳过日志文件清理"
        fi
    else
        echo -e "${YELLOW}•${NC} 有 $LOG_FILES 个日志文件（都小于 1MB）"
    fi
else
    echo -e "${YELLOW}•${NC} 无日志文件"
fi

echo ""

# 5. IDE/编辑器缓存
echo "5️⃣  清理 IDE 缓存"
echo "--------------------------------"

# .vscode 缓存（保留配置）
if [ -d ".vscode" ]; then
    if [ -d ".vscode/.cache" ]; then
        rm -rf .vscode/.cache
        echo -e "${GREEN}✓${NC} 清理 .vscode/.cache"
    fi
fi

# .idea 缓存
if [ -d ".idea" ]; then
    IDEA_SIZE=$(du -sh .idea 2>/dev/null | cut -f1)
    echo -e "${YELLOW}!${NC} 发现 .idea 目录 ($IDEA_SIZE)"
    echo "   (通常应该被 .gitignore 忽略)"
fi

echo ""

# 统计清理后的文件数
AFTER_COUNT=$(find . -type f -not -path "*/.git/*" 2>/dev/null | wc -l | tr -d ' ')

# 6. 总结
echo "================================"
echo -e "${GREEN}✓ 清理完成${NC}"
echo ""
echo "📊 统计:"
echo "   清理前: $BEFORE_COUNT 个文件"
echo "   清理后: $AFTER_COUNT 个文件"
echo "   减少: $((BEFORE_COUNT - AFTER_COUNT)) 个文件"
echo "   清理项: $CLEANED_COUNT 项"
echo ""

# 7. 建议
echo "💡 下一步建议:"
echo "--------------------------------"
echo "1. 重启 Cursor IDE 以应用更改"
echo "2. 清除 Cursor IDE 缓存:"
echo "   rm -rf ~/Library/Application\ Support/Cursor/Cache/*"
echo "   rm -rf ~/Library/Application\ Support/Cursor/CachedData/*"
echo "3. 在 Cursor 中重新加载窗口:"
echo "   Cmd + Shift + P → 'Developer: Reload Window'"
echo ""
echo "4. 验证性能提升:"
echo "   ./scripts/check-cursor-performance.sh"
echo ""

# 8. 自动化建议
echo "🔄 自动化清理:"
echo "--------------------------------"
echo "将此脚本添加到每日工作流中，或设置 cron 任务:"
echo "   # 每天早上 9 点清理缓存"
echo "   0 9 * * * cd $PROJECT_ROOT && ./scripts/clean-caches.sh"
echo ""
