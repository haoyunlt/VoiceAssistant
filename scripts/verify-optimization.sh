#!/bin/bash
# 验证 Cursor 性能优化脚本
# 用途：检查优化配置是否正确生效

set -e

echo "🔍 开始验证 Cursor 性能优化..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 验证结果统计
PASSED=0
FAILED=0

# 检查函数
check_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $description${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ $description${NC}"
        echo -e "   ${YELLOW}文件不存在: $file${NC}"
        ((FAILED++))
        return 1
    fi
}

check_dir() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✅ $description${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ $description${NC}"
        echo -e "   ${YELLOW}目录不存在: $dir${NC}"
        ((FAILED++))
        return 1
    fi
}

check_file_count() {
    local pattern=$1
    local max_count=$2
    local description=$3

    local count=$(find . -maxdepth 1 -name "$pattern" 2>/dev/null | wc -l | tr -d ' ')

    if [ "$count" -le "$max_count" ]; then
        echo -e "${GREEN}✅ $description (当前: $count, 预期: ≤ $max_count)${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ $description (当前: $count, 预期: ≤ $max_count)${NC}"
        ((FAILED++))
        return 1
    fi
}

check_archived() {
    local file=$1
    local description=$2

    if [ -f "docs/reports/archive/$file" ]; then
        echo -e "${GREEN}✅ $description 已归档${NC}"
        ((PASSED++))
        return 0
    elif [ -f "$file" ] || [ -f "docs/$file" ]; then
        echo -e "${RED}❌ $description 未归档${NC}"
        echo -e "   ${YELLOW}文件仍在主目录: $file${NC}"
        ((FAILED++))
        return 1
    else
        echo -e "${YELLOW}⚠️  $description 不存在${NC}"
        return 0
    fi
}

echo "📝 1. 检查配置文件"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file ".cursorignore" ".cursorignore 配置文件"
check_file ".gitattributes" ".gitattributes 配置文件"
echo ""

echo "📚 2. 检查新建文档"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "docs/CURSOR_PERFORMANCE_OPTIMIZATION.md" "性能优化指南"
check_file "docs/ARCHIVE_SUMMARY.md" "归档总结"
check_file "docs/reports/archive/README.md" "归档索引"
check_file "OPTIMIZATION_COMPLETE.md" "优化完成报告"
echo ""

echo "📁 3. 检查归档目录"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_dir "docs/reports" "reports 目录"
check_dir "docs/reports/archive" "archive 目录"

# 检查归档文件数量
archive_count=$(ls -1 docs/reports/archive/*.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$archive_count" -ge 40 ]; then
    echo -e "${GREEN}✅ 归档文件数量符合预期 (当前: $archive_count, 预期: ≥ 40)${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ 归档文件数量不足 (当前: $archive_count, 预期: ≥ 40)${NC}"
    ((FAILED++))
fi
echo ""

echo "🧹 4. 检查文档清理情况"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file_count "*.md" 10 "根目录 Markdown 文件数量"
check_file_count "docs/*.md" 6 "docs/ 目录 Markdown 文件数量"
echo ""

echo "📦 5. 验证关键文件已归档"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_archived "DETAILED_WEEK_PLAN.md" "DETAILED_WEEK_PLAN.md"
check_archived "PHASE1_WEEK1_EXECUTION.md" "PHASE1_WEEK1_EXECUTION.md"
check_archived "COMPLETION_SUMMARY.md" "COMPLETION_SUMMARY.md"
check_archived "P0_PROGRESS_REPORT.md" "P0_PROGRESS_REPORT.md"
check_archived "SERVICE_COMPLETION_REPORT.md" "SERVICE_COMPLETION_REPORT.md"
echo ""

echo "🔍 6. 检查 .cursorignore 内容"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f ".cursorignore" ]; then
    # 检查关键规则
    if grep -q "node_modules/" .cursorignore; then
        echo -e "${GREEN}✅ 包含 node_modules/ 规则${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ 缺少 node_modules/ 规则${NC}"
        ((FAILED++))
    fi

    if grep -q "__pycache__/" .cursorignore; then
        echo -e "${GREEN}✅ 包含 __pycache__/ 规则${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ 缺少 __pycache__/ 规则${NC}"
        ((FAILED++))
    fi

    if grep -q "*.pb.go" .cursorignore; then
        echo -e "${GREEN}✅ 包含 *.pb.go 规则${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ 缺少 *.pb.go 规则${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ .cursorignore 文件不存在${NC}"
    ((FAILED+=3))
fi
echo ""

echo "📊 7. 统计信息"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 统计根目录 Markdown 文件
root_md_count=$(ls -1 *.md 2>/dev/null | wc -l | tr -d ' ')
echo "   根目录 Markdown 文件: $root_md_count 个"

# 统计 docs/ 目录 Markdown 文件
docs_md_count=$(ls -1 docs/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "   docs/ 目录 Markdown 文件: $docs_md_count 个"

# 统计归档文件
archive_md_count=$(ls -1 docs/reports/archive/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "   归档目录文件数: $archive_md_count 个"

# 统计 Python 缓存
pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
echo "   __pycache__ 目录数: $pycache_count 个"

# 统计 node_modules
node_modules_count=$(find . -type d -name "node_modules" 2>/dev/null | wc -l | tr -d ' ')
echo "   node_modules 目录数: $node_modules_count 个"

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ 验证结果总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 恭喜！所有检查都通过了！${NC}"
    echo ""
    echo "📝 后续步骤:"
    echo "   1. 重启 Cursor 编辑器 (⌘ + Q)"
    echo "   2. 等待重新索引完成 (< 5 分钟)"
    echo "   3. 测试搜索性能 (⌘ + P / ⌘ + Shift + F)"
    echo "   4. 查看优化指南: docs/CURSOR_PERFORMANCE_OPTIMIZATION.md"
    echo ""
    exit 0
else
    echo -e "${RED}❌ 有 $FAILED 项检查失败，请修复后重试${NC}"
    echo ""
    echo "📝 修复建议:"
    echo "   1. 检查失败的项目"
    echo "   2. 重新执行归档操作"
    echo "   3. 确认配置文件已创建"
    echo "   4. 查看文档: docs/CURSOR_PERFORMANCE_OPTIMIZATION.md"
    echo ""
    exit 1
fi
