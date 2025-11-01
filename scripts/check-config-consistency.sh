#!/bin/bash
# 检查配置文件一致性

set -e

echo "🔍 检查配置文件一致性..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# 检查端口一致性
echo "📊 检查端口配置..."

check_port() {
    local service=$1
    local expected_port=$2
    
    # 在 services.yaml 中检查
    port1=$(grep -A 2 "$service:" configs/services.yaml | grep "localhost:" | grep -oE '[0-9]+' || echo "")
    
    # 在 algo-services.yaml 中检查（如果存在）
    port2=$(grep -A 2 "$service:" configs/algo-services.yaml 2>/dev/null | grep "localhost:" | grep -oE '[0-9]+' || echo "")
    
    if [ -n "$port1" ] && [ -n "$port2" ] && [ "$port1" != "$port2" ]; then
        echo -e "${RED}❌ 错误: $service 端口不一致: services.yaml($port1) vs algo-services.yaml($port2)${NC}"
        ((ERRORS++))
    elif [ -n "$port1" ] && [ "$port1" == "$expected_port" ]; then
        echo -e "${GREEN}✅ $service 端口正确: $port1${NC}"
    elif [ -n "$port1" ]; then
        echo -e "${YELLOW}⚠️  警告: $service 端口可能不正确: 期望$expected_port, 实际$port1${NC}"
        ((WARNINGS++))
    fi
}

check_port "multimodal-engine" "8008"
check_port "agent-engine" "8010"
check_port "retrieval-service" "8012"
check_port "model-adapter" "8005"
check_port "knowledge-service" "8006"
check_port "voice-engine" "8004"
check_port "vector-store-adapter" "8009"
check_port "indexing-service" "8011"

# 检查超时配置
echo ""
echo "⏱️  检查超时配置..."

check_timeout() {
    local service=$1
    local min_timeout=$2
    local max_timeout=$3
    
    timeout=$(grep -A 2 "$service:" configs/services.yaml | grep "timeout:" | grep -oE '[0-9]+' || echo "0")
    
    if [ "$timeout" -lt "$min_timeout" ] || [ "$timeout" -gt "$max_timeout" ]; then
        echo -e "${YELLOW}⚠️  警告: $service 超时可能不合理: ${timeout}s (推荐 ${min_timeout}-${max_timeout}s)${NC}"
        ((WARNINGS++))
    else
        echo -e "${GREEN}✅ $service 超时合理: ${timeout}s${NC}"
    fi
}

check_timeout "retrieval-service" 10 30
check_timeout "agent-engine" 60 120
check_timeout "model-adapter" 30 60

# 检查废弃服务引用
echo ""
echo "🗑️  检查废弃服务引用..."

if grep -r "rag-engine" configs/ pkg/ cmd/ --include="*.go" --include="*.yaml" 2>/dev/null | grep -v "^#" | grep -v "已废弃" | grep -v "已合并" > /dev/null; then
    echo -e "${YELLOW}⚠️  警告: 发现 rag-engine 引用（已废弃，应使用 knowledge-service）${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✅ 未发现废弃服务引用${NC}"
fi

# 总结
echo ""
echo "======================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有检查通过！${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  发现 $WARNINGS 个警告${NC}"
    exit 0
else
    echo -e "${RED}❌ 发现 $ERRORS 个错误和 $WARNINGS 个警告${NC}"
    exit 1
fi
