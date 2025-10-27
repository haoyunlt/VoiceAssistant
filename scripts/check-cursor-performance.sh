#!/bin/bash
# Cursor 性能优化验证脚本

set -e

echo "🔍 Cursor 性能优化验证"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 项目路径: $PROJECT_ROOT"
echo ""

# 1. 检查 .cursorignore 文件
echo "1️⃣  检查 .cursorignore 配置"
echo "--------------------------------"
if [ -f ".cursorignore" ]; then
    IGNORE_LINES=$(grep -v '^#' .cursorignore | grep -v '^$' | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} .cursorignore 存在 (${IGNORE_LINES} 条规则)"
else
    echo -e "${RED}✗${NC} .cursorignore 不存在"
fi
echo ""

# 2. 统计文件总数
echo "2️⃣  统计项目文件"
echo "--------------------------------"

# 统计所有文件（包括被忽略的）
TOTAL_FILES=$(find . -type f \
    -not -path "*/.git/*" \
    2>/dev/null | wc -l | tr -d ' ')
echo "   总文件数: ${TOTAL_FILES}"

# 统计应该被索引的文件（排除 .gitignore 和 .cursorignore）
INDEXED_FILES=$(find . -type f \
    -not -path "*/.git/*" \
    -not -path "*/node_modules/*" \
    -not -path "*/.venv/*" \
    -not -path "*/venv/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/vendor/*" \
    -not -path "*/.next/*" \
    -not -path "*/dist/*" \
    -not -path "*/build/*" \
    -not -name "*.log" \
    -not -name "SPRINT*.md" \
    -not -name "*_PLAN.md" \
    -not -name "*_SUMMARY.md" \
    -not -name "*_REPORT.md" \
    -not -name "VOICEHELPER_MIGRATION_*.md" \
    2>/dev/null | wc -l | tr -d ' ')

REDUCTION_RATE=$(echo "scale=1; ($TOTAL_FILES - $INDEXED_FILES) * 100 / $TOTAL_FILES" | bc)

echo "   应索引文件: ${INDEXED_FILES}"
echo -e "   ${GREEN}减少索引: ${REDUCTION_RATE}%${NC}"
echo ""

# 3. 检查大型文档
echo "3️⃣  检查大型文档（被忽略）"
echo "--------------------------------"

LARGE_DOCS=$(find . -maxdepth 1 -type f \
    \( -name "SPRINT*.md" \
    -or -name "*_PLAN.md" \
    -or -name "*_SUMMARY.md" \
    -or -name "*_REPORT.md" \
    -or -name "VOICEHELPER_MIGRATION_*.md" \) \
    2>/dev/null | wc -l | tr -d ' ')

if [ "$LARGE_DOCS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} 找到 ${LARGE_DOCS} 个大型文档（已被忽略）"
    find . -maxdepth 1 -type f \
        \( -name "SPRINT*.md" \
        -or -name "*_PLAN.md" \
        -or -name "*_SUMMARY.md" \
        -or -name "*_REPORT.md" \
        -or -name "VOICEHELPER_MIGRATION_*.md" \) \
        -exec basename {} \; 2>/dev/null | head -5 | sed 's/^/      - /'
    if [ "$LARGE_DOCS" -gt 5 ]; then
        echo "      ..."
    fi
else
    echo -e "${YELLOW}!${NC} 未找到需要忽略的大型文档"
fi
echo ""

# 4. 检查数据目录
echo "4️⃣  检查数据目录（应被忽略）"
echo "--------------------------------"

DATA_DIRS=("node_modules" ".venv" "venv" "__pycache__" "vendor" ".next" "dist" "build" \
           "milvus_data" "qdrant_data" "kafka_data" "clickhouse_data" "redis_data")

FOUND_DATA_DIRS=0
for dir in "${DATA_DIRS[@]}"; do
    if find . -type d -name "$dir" 2>/dev/null | grep -q .; then
        FOUND_DATA_DIRS=$((FOUND_DATA_DIRS + 1))
    fi
done

if [ $FOUND_DATA_DIRS -gt 0 ]; then
    echo -e "${GREEN}✓${NC} 找到 ${FOUND_DATA_DIRS} 个数据目录（已被忽略）"
    for dir in "${DATA_DIRS[@]}"; do
        if find . -type d -name "$dir" 2>/dev/null | grep -q .; then
            echo "      - $dir"
        fi
    done | head -5
else
    echo -e "${GREEN}✓${NC} 未找到需要忽略的数据目录（很好！）"
fi
echo ""

# 5. 按类型统计文件
echo "5️⃣  文件类型分布（应索引的）"
echo "--------------------------------"

echo "   源代码文件:"
for ext in py go ts tsx js jsx; do
    COUNT=$(find . -type f -name "*.$ext" \
        -not -path "*/.git/*" \
        -not -path "*/node_modules/*" \
        -not -path "*/.venv/*" \
        -not -path "*/venv/*" \
        -not -path "*/__pycache__/*" \
        -not -path "*/vendor/*" \
        2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 0 ]; then
        printf "      %-6s: %4d files\n" "$ext" "$COUNT"
    fi
done

echo ""
echo "   配置文件:"
for ext in yaml yml json toml; do
    COUNT=$(find . -type f -name "*.$ext" \
        -not -path "*/.git/*" \
        -not -path "*/node_modules/*" \
        -not -path "*/.venv/*" \
        -not -path "*/vendor/*" \
        2>/dev/null | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 0 ]; then
        printf "      %-6s: %4d files\n" "$ext" "$COUNT"
    fi
done
echo ""

# 6. 内存检查
echo "6️⃣  Cursor 进程检查"
echo "--------------------------------"

if pgrep -f "Cursor" > /dev/null; then
    echo -e "${GREEN}✓${NC} Cursor 正在运行"

    # macOS 特定
    if [[ "$OSTYPE" == "darwin"* ]]; then
        CURSOR_MEM=$(ps aux | grep -i "[C]ursor" | awk '{sum+=$6} END {printf "%.1f", sum/1024}')
        echo "   内存使用: ${CURSOR_MEM} MB"
    else
        echo "   (内存检查仅支持 macOS)"
    fi
else
    echo -e "${YELLOW}!${NC} Cursor 未运行"
fi
echo ""

# 7. 优化建议
echo "7️⃣  优化建议"
echo "--------------------------------"

# 检查是否有 .git 目录过大
GIT_SIZE=$(du -sh .git 2>/dev/null | cut -f1)
echo "   .git 目录大小: $GIT_SIZE"

# 检查是否有大文件
LARGE_FILES=$(find . -type f -size +10M \
    -not -path "*/.git/*" \
    2>/dev/null | wc -l | tr -d ' ')

if [ "$LARGE_FILES" -gt 0 ]; then
    echo -e "   ${YELLOW}!${NC} 发现 ${LARGE_FILES} 个大文件 (>10MB)"
    echo "     运行以下命令查看:"
    echo "     find . -type f -size +10M -not -path '*/.git/*' -exec ls -lh {} +"
fi
echo ""

# 8. 下一步操作
echo "8️⃣  下一步操作"
echo "--------------------------------"
echo -e "${BLUE}建议操作:${NC}"
echo "   1. 重启 Cursor IDE"
echo "   2. 清除缓存:"
echo "      rm -rf ~/Library/Application\ Support/Cursor/Cache/*"
echo "   3. 在 Cursor 中重新加载:"
echo "      Cmd + Shift + P → 'Developer: Reload Window'"
echo ""

# 9. 性能基准
echo "9️⃣  性能基准测试"
echo "--------------------------------"
echo "   执行文件搜索测试..."

START_TIME=$(date +%s%N)
find . -type f -name "*.py" \
    -not -path "*/.git/*" \
    -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" \
    > /dev/null 2>&1
END_TIME=$(date +%s%N)
SEARCH_TIME=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000" | bc)

echo "   Python 文件搜索: ${SEARCH_TIME}ms"

if (( $(echo "$SEARCH_TIME < 100" | bc -l) )); then
    echo -e "   ${GREEN}✓ 搜索性能良好${NC}"
elif (( $(echo "$SEARCH_TIME < 500" | bc -l) )); then
    echo -e "   ${YELLOW}! 搜索性能一般${NC}"
else
    echo -e "   ${RED}✗ 搜索性能较慢，建议进一步优化${NC}"
fi
echo ""

# 总结
echo "================================"
echo -e "${GREEN}✓ 优化验证完成${NC}"
echo ""
echo "📊 摘要:"
echo "   - 总文件数: ${TOTAL_FILES}"
echo "   - 索引文件: ${INDEXED_FILES}"
echo "   - 优化率: ${REDUCTION_RATE}%"
echo ""
echo "📖 查看详细优化指南:"
echo "   cat CURSOR_PERFORMANCE_OPTIMIZATION.md"
echo ""
