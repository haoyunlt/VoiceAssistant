#!/bin/bash
# Cursor IDE 一键性能优化脚本

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

clear
echo -e "${BOLD}${CYAN}"
echo "╔════════════════════════════════════════════════╗"
echo "║   Cursor IDE 性能优化脚本                      ║"
echo "║   VoiceAssistant Project                       ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# 检查是否是 macOS
OS_TYPE="$(uname -s)"
echo -e "${BLUE}检测到操作系统:${NC} $OS_TYPE"
echo ""

# ====================================
# 步骤 1: 检查 Cursor 是否运行
# ====================================
echo -e "${BOLD}[1/6] 检查 Cursor 进程${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CURSOR_RUNNING=false
if pgrep -f "Cursor" > /dev/null; then
    CURSOR_RUNNING=true
    echo -e "${YELLOW}⚠ Cursor 正在运行${NC}"
    echo ""
    echo "为获得最佳优化效果，建议先关闭 Cursor。"
    echo ""
    read -p "是否现在关闭 Cursor? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            killall Cursor 2>/dev/null || true
            sleep 2
            echo -e "${GREEN}✓ 已关闭 Cursor${NC}"
        else
            echo -e "${YELLOW}! 请手动关闭 Cursor 后按回车继续${NC}"
            read
        fi
        CURSOR_RUNNING=false
    else
        echo -e "${YELLOW}! 将在 Cursor 运行时继续优化${NC}"
    fi
else
    echo -e "${GREEN}✓ Cursor 未运行${NC}"
fi
echo ""

# ====================================
# 步骤 2: 清理项目缓存
# ====================================
echo -e "${BOLD}[2/6] 清理项目缓存${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CLEANED_SIZE=0

# Python 缓存
echo -n "清理 Python 缓存... "
BEFORE_SIZE=$(du -sk . 2>/dev/null | cut -f1)

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true
rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true

AFTER_SIZE=$(du -sk . 2>/dev/null | cut -f1)
SAVED=$((BEFORE_SIZE - AFTER_SIZE))
CLEANED_SIZE=$((CLEANED_SIZE + SAVED))
echo -e "${GREEN}✓${NC} 释放 $((SAVED / 1024))MB"

# Go 缓存
echo -n "清理 Go 缓存... "
find . -type f -name "*.test" -delete 2>/dev/null || true
find . -type f \( -name "*.out" -o -name "*.coverprofile" \) -not -path "*/.git/*" -delete 2>/dev/null || true
echo -e "${GREEN}✓${NC}"

# 临时文件
echo -n "清理临时文件... "
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -type f \( -name "*.swp" -o -name "*.swo" -o -name "*~" \) -delete 2>/dev/null || true
find . -type f \( -name "*.tmp" -o -name "*.temp" \) -delete 2>/dev/null || true
echo -e "${GREEN}✓${NC}"

echo -e "${GREEN}✓ 项目缓存清理完成 (共释放 $((CLEANED_SIZE / 1024))MB)${NC}"
echo ""

# ====================================
# 步骤 3: 清理 Cursor 应用缓存
# ====================================
echo -e "${BOLD}[3/6] 清理 Cursor 应用缓存${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$OS_TYPE" == "Darwin" ]]; then
    CURSOR_CACHE="$HOME/Library/Application Support/Cursor"

    if [ -d "$CURSOR_CACHE" ]; then
        CACHE_SIZE=$(du -sh "$CURSOR_CACHE/Cache" 2>/dev/null | cut -f1 || echo "0K")

        echo -n "清理 Cursor 缓存目录... "
        rm -rf "$CURSOR_CACHE/Cache/"* 2>/dev/null || true
        rm -rf "$CURSOR_CACHE/CachedData/"* 2>/dev/null || true
        rm -rf "$CURSOR_CACHE/Code Cache/"* 2>/dev/null || true
        rm -rf "$CURSOR_CACHE/GPUCache/"* 2>/dev/null || true
        echo -e "${GREEN}✓${NC} 释放 $CACHE_SIZE"

        # 可选：清理日志
        if [ -d "$CURSOR_CACHE/logs" ]; then
            LOG_SIZE=$(du -sh "$CURSOR_CACHE/logs" 2>/dev/null | cut -f1 || echo "0K")
            if [ "$LOG_SIZE" != "0K" ]; then
                echo -n "清理日志文件 ($LOG_SIZE)... "
                rm -rf "$CURSOR_CACHE/logs/"* 2>/dev/null || true
                echo -e "${GREEN}✓${NC}"
            fi
        fi

        echo -e "${GREEN}✓ Cursor 应用缓存清理完成${NC}"
    else
        echo -e "${YELLOW}! Cursor 缓存目录不存在${NC}"
    fi
elif [[ "$OS_TYPE" == "Linux" ]]; then
    CURSOR_CACHE="$HOME/.config/Cursor"
    if [ -d "$CURSOR_CACHE" ]; then
        rm -rf "$CURSOR_CACHE/Cache/"* 2>/dev/null || true
        rm -rf "$CURSOR_CACHE/CachedData/"* 2>/dev/null || true
        echo -e "${GREEN}✓ Cursor 应用缓存清理完成${NC}"
    fi
else
    echo -e "${YELLOW}! Windows 系统请手动清理：%APPDATA%\\Cursor\\Cache${NC}"
fi
echo ""

# ====================================
# 步骤 4: 验证 .cursorignore 配置
# ====================================
echo -e "${BOLD}[4/6] 验证 .cursorignore 配置${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f ".cursorignore" ]; then
    IGNORE_RULES=$(grep -v '^#' .cursorignore | grep -v '^$' | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} .cursorignore 存在 (${IGNORE_RULES} 条规则)"

    # 检查关键规则
    echo ""
    echo "关键规则检查:"

    MISSING_RULES=()

    if ! grep -q "\.mypy_cache" .cursorignore; then
        MISSING_RULES+=(".mypy_cache")
    fi
    if ! grep -q "__pycache__" .cursorignore; then
        MISSING_RULES+=("__pycache__")
    fi
    if ! grep -q "node_modules" .cursorignore; then
        MISSING_RULES+=("node_modules")
    fi
    if ! grep -q "\.venv" .cursorignore; then
        MISSING_RULES+=(".venv")
    fi

    if [ ${#MISSING_RULES[@]} -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} 所有关键规则已配置"
    else
        echo -e "  ${YELLOW}!${NC} 缺少以下规则:"
        for rule in "${MISSING_RULES[@]}"; do
            echo "    - $rule"
        done
    fi
else
    echo -e "${RED}✗${NC} .cursorignore 不存在"
    echo -e "${YELLOW}! 建议创建 .cursorignore 文件${NC}"
fi
echo ""

# ====================================
# 步骤 5: 性能统计
# ====================================
echo -e "${BOLD}[5/6] 性能统计${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 文件数统计
TOTAL_FILES=$(find . -type f -not -path "*/.git/*" 2>/dev/null | wc -l | tr -d ' ')
INDEXED_FILES=$(find . -type f \
    -not -path "*/.git/*" \
    -not -path "*/node_modules/*" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.mypy_cache/*" \
    -not -path "*/.pytest_cache/*" \
    2>/dev/null | wc -l | tr -d ' ')

REDUCTION=$((TOTAL_FILES - INDEXED_FILES))
REDUCTION_RATE=$(echo "scale=1; $REDUCTION * 100 / $TOTAL_FILES" | bc 2>/dev/null || echo "N/A")

echo "文件统计:"
echo "  总文件数: $TOTAL_FILES"
echo "  需索引: $INDEXED_FILES"
echo -e "  ${GREEN}优化: ${REDUCTION_RATE}%${NC} ($REDUCTION 个文件)"
echo ""

# 搜索速度测试
echo -n "搜索性能测试... "
START_TIME=$(date +%s%N 2>/dev/null || date +%s)
find . -type f -name "*.py" \
    -not -path "*/.git/*" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    > /dev/null 2>&1
END_TIME=$(date +%s%N 2>/dev/null || date +%s)

if command -v bc > /dev/null 2>&1; then
    SEARCH_TIME=$(echo "scale=1; ($END_TIME - $START_TIME) / 1000000" | bc 2>/dev/null || echo "N/A")
    echo -e "${GREEN}✓${NC} ${SEARCH_TIME}ms"
else
    echo -e "${GREEN}✓${NC} 完成"
fi
echo ""

# ====================================
# 步骤 6: 生成性能报告
# ====================================
echo -e "${BOLD}[6/6] 生成性能报告${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

REPORT_FILE="cursor-performance-report-$(date +%Y%m%d-%H%M%S).txt"
cat > "$REPORT_FILE" <<EOF
Cursor IDE 性能优化报告
===============================================
生成时间: $(date '+%Y-%m-%d %H:%M:%S')
项目路径: $PROJECT_ROOT
操作系统: $OS_TYPE

优化结果
-----------------------------------------------
项目文件总数: $TOTAL_FILES
需索引文件数: $INDEXED_FILES
优化率: ${REDUCTION_RATE}%
释放磁盘空间: $((CLEANED_SIZE / 1024))MB

优化项目
-----------------------------------------------
✓ 清理 Python 缓存 (__pycache__, .mypy_cache, .pytest_cache)
✓ 清理 Go 测试和覆盖率文件
✓ 清理临时文件 (.DS_Store, *.swp, *.tmp)
✓ 清理 Cursor 应用缓存
✓ 验证 .cursorignore 配置 ($IGNORE_RULES 条规则)

建议
-----------------------------------------------
1. 重启 Cursor IDE 以应用所有更改
2. 在 Cursor 中执行: Cmd + Shift + P → "Developer: Reload Window"
3. 定期运行: ./scripts/clean-caches.sh
4. 查看详细指南: CURSOR_SETTINGS_GUIDE.md

EOF

echo -e "${GREEN}✓ 报告已生成: $REPORT_FILE${NC}"
echo ""

# ====================================
# 完成总结
# ====================================
echo ""
echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════════════════╗"
echo "║   ✓ 优化完成                                   ║"
echo "╚════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

echo -e "${BOLD}📊 优化摘要:${NC}"
echo "  • 释放空间: $((CLEANED_SIZE / 1024))MB"
echo "  • 优化率: ${REDUCTION_RATE}%"
echo "  • 减少索引: $REDUCTION 个文件"
echo ""

echo -e "${BOLD}🚀 下一步操作:${NC}"
echo ""

if [ "$CURSOR_RUNNING" = true ]; then
    echo "  1. 在 Cursor 中重新加载窗口:"
    echo -e "     ${CYAN}Cmd + Shift + P → 'Developer: Reload Window'${NC}"
else
    echo "  1. 启动 Cursor IDE"
fi

echo ""
echo "  2. 验证性能提升:"
echo -e "     ${CYAN}./scripts/check-cursor-performance.sh${NC}"
echo ""

echo "  3. 查看详细配置指南:"
echo -e "     ${CYAN}cat CURSOR_SETTINGS_GUIDE.md${NC}"
echo ""

echo "  4. 查看完整报告:"
echo -e "     ${CYAN}cat $REPORT_FILE${NC}"
echo ""

echo -e "${BOLD}💡 提示:${NC}"
echo "  • 定期运行 ${CYAN}./scripts/clean-caches.sh${NC} 保持最佳性能"
echo "  • 对于大型项目，考虑只打开需要的服务目录"
echo "  • 遇到问题查看: CURSOR_SETTINGS_GUIDE.md"
echo ""

# 询问是否自动打开 Cursor
if [ "$CURSOR_RUNNING" = false ]; then
    echo ""
    read -p "是否现在打开 Cursor? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            open -a Cursor "$PROJECT_ROOT" 2>/dev/null || open -a "Cursor" "$PROJECT_ROOT" 2>/dev/null || echo "请手动打开 Cursor"
        else
            cursor . 2>/dev/null || echo "请手动打开 Cursor"
        fi
    fi
fi

echo ""
echo -e "${GREEN}✓ 优化脚本执行完毕${NC}"
echo ""
