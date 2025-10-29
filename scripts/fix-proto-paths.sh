#!/usr/bin/env bash

set -euo pipefail

# 代码审查自动修复脚本
# 修复proto包路径不一致问题

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔧 VoiceHelper Proto路径修复脚本"
echo "=================================="
echo ""

cd "$PROJECT_ROOT"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否在正确的目录
if [ ! -f "go.mod" ]; then
    echo -e "${RED}错误: 请在项目根目录执行此脚本${NC}"
    exit 1
fi

# 获取当前模块名
MODULE_NAME=$(grep "^module" go.mod | awk '{print $2}')
echo -e "${GREEN}✓${NC} 检测到模块名: ${MODULE_NAME}"

# 检查proto目录
if [ ! -d "api/proto" ]; then
    echo -e "${RED}错误: 找不到 api/proto 目录${NC}"
    exit 1
fi

echo ""
echo "📋 待修复的问题:"
echo "  1. Proto文件中的 go_package 路径"
echo "  2. Go代码中的 import 语句"
echo "  3. 重新生成 proto 代码"
echo ""

read -p "是否继续修复? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "🔄 开始修复..."
echo ""

# 步骤1: 备份
echo -e "${YELLOW}[1/5]${NC} 创建备份..."
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r api/proto "$BACKUP_DIR/"
echo -e "${GREEN}✓${NC} 备份已创建: $BACKUP_DIR"

# 步骤2: 修复proto文件
echo ""
echo -e "${YELLOW}[2/5]${NC} 修复proto文件的go_package..."
PROTO_FILES=$(find api/proto -name "*.proto" -type f)
FIXED_COUNT=0

for proto_file in $PROTO_FILES; do
    if grep -q 'option go_package.*voiceassistant' "$proto_file"; then
        sed -i.bak 's|option go_package = "voiceassistant/|option go_package = "'$MODULE_NAME'/|g' "$proto_file"
        rm -f "${proto_file}.bak"
        echo -e "  ${GREEN}✓${NC} $proto_file"
        ((FIXED_COUNT++))
    fi
done

echo -e "${GREEN}✓${NC} 已修复 $FIXED_COUNT 个proto文件"

# 步骤3: 重新生成proto代码
echo ""
echo -e "${YELLOW}[3/5]${NC} 重新生成proto代码..."

if command -v protoc &> /dev/null; then
    # 检查是否有Makefile
    if [ -f "Makefile" ] && grep -q "proto-gen" Makefile; then
        echo "  使用 Makefile..."
        make proto-gen
    else
        echo "  直接使用 protoc..."
        for proto_file in $PROTO_FILES; do
            protoc --go_out=. --go_opt=paths=source_relative \
                   --go-grpc_out=. --go-grpc_opt=paths=source_relative \
                   "$proto_file" || true
        done
    fi
    echo -e "${GREEN}✓${NC} Proto代码已重新生成"
else
    echo -e "${YELLOW}⚠${NC} 未找到protoc命令，跳过生成步骤"
    echo "  请手动运行: make proto-gen"
fi

# 步骤4: 修复Go代码import
echo ""
echo -e "${YELLOW}[4/5]${NC} 修复Go代码中的import语句..."

GO_DIRS=("pkg/clients" "cmd" "internal")
IMPORT_FIXED=0

for dir in "${GO_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        GO_FILES=$(find "$dir" -name "*.go" -type f 2>/dev/null || true)
        for go_file in $GO_FILES; do
            if grep -q 'voiceassistant/api/proto' "$go_file"; then
                sed -i.bak 's|voiceassistant/api/proto|'$MODULE_NAME'/api/proto|g' "$go_file"
                rm -f "${go_file}.bak"
                echo -e "  ${GREEN}✓${NC} $go_file"
                ((IMPORT_FIXED++))
            fi
        done
    fi
done

echo -e "${GREEN}✓${NC} 已修复 $IMPORT_FIXED 个Go文件的import"

# 步骤5: 验证修复
echo ""
echo -e "${YELLOW}[5/5]${NC} 验证修复..."

# 检查是否还有voiceassistant引用
REMAINING=$(grep -r "voiceassistant/api/proto" pkg cmd internal 2>/dev/null | grep -v ".pb.go" | wc -l || true)

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} 所有文件已修复"
else
    echo -e "${YELLOW}⚠${NC} 仍有 $REMAINING 处引用需要手动检查"
fi

# 运行go mod tidy
echo ""
echo "📦 运行 go mod tidy..."
if go mod tidy; then
    echo -e "${GREEN}✓${NC} go mod tidy 成功"
else
    echo -e "${RED}✗${NC} go mod tidy 失败，请检查错误"
fi

# 尝试编译
echo ""
echo "🔨 尝试编译..."
if go build ./cmd/... 2>&1 | head -20; then
    echo -e "${GREEN}✓${NC} 编译成功"
else
    echo -e "${YELLOW}⚠${NC} 编译有警告或错误，请检查"
fi

echo ""
echo "=================================="
echo -e "${GREEN}✅ 修复完成!${NC}"
echo ""
echo "📝 下一步操作："
echo "  1. 检查修改: git diff"
echo "  2. 运行测试: go test ./..."
echo "  3. 提交更改: git add . && git commit -m 'fix: unify proto package paths'"
echo ""
echo "📂 备份位置: $BACKUP_DIR"
echo ""
