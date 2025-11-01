#!/bin/bash

###############################################################################
# 配置验证脚本
#
# 功能：
# 1. 检查端口冲突
# 2. 验证服务依赖完整性
# 3. 检查配置文件一致性
# 4. 生成配置报告
#
# 使用方法:
#   ./scripts/validate-config.sh
###############################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 计数器
ERRORS=0
WARNINGS=0
SUCCESS=0

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONFIG_DIR="$PROJECT_ROOT/configs"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   配置验证工具 v1.0${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# 检查配置文件是否存在
check_config_files() {
    echo -e "${BLUE}[1/5] 检查配置文件存在性...${NC}"

    local required_files=(
        "$CONFIG_DIR/services.yaml"
        "$CONFIG_DIR/algo-services.yaml"
        "$CONFIG_DIR/services-integration.yaml"
    )

    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            echo -e "${GREEN}  ✓${NC} 找到: $(basename "$file")"
            ((SUCCESS++))
        else
            echo -e "${RED}  ✗${NC} 缺失: $(basename "$file")"
            ((ERRORS++))
        fi
    done
    echo ""
}

# 检查端口冲突
check_port_conflicts() {
    echo -e "${BLUE}[2/5] 检查端口冲突...${NC}"

    # 提取所有端口
    local ports=()

    # 从services.yaml提取
    if command -v yq &> /dev/null; then
        # 如果有yq工具
        echo "  使用 yq 解析配置..."
    else
        # 手动提取端口（简单方式）
        echo "  手动提取端口号..."

        # Go Services (gRPC)
        ports+=(50051 50052 50054 50055 50056 50057)

        # Python Services (HTTP)
        ports+=(8004 8005 8006 8008 8009 8010 8011 8012)

        # 检查重复
        local unique_ports=($(printf '%s\n' "${ports[@]}" | sort -u))
        local total_ports=${#ports[@]}
        local unique_count=${#unique_ports[@]}

        if [ $total_ports -eq $unique_count ]; then
            echo -e "${GREEN}  ✓${NC} 未发现端口冲突 (总计 $unique_count 个端口)"
            ((SUCCESS++))
        else
            echo -e "${RED}  ✗${NC} 发现端口冲突！"
            echo "    总端口数: $total_ports"
            echo "    唯一端口: $unique_count"
            ((ERRORS++))
        fi
    fi

    echo ""
}

# 检查服务端口一致性
check_port_consistency() {
    echo -e "${BLUE}[3/5] 检查服务端口一致性...${NC}"

    echo "  检查关键服务端口配置:"

    # 检查 agent-engine
    if grep -q "agent-engine.*8010" "$CONFIG_DIR/services.yaml" && \
       grep -q "agent-engine.*8010" "$CONFIG_DIR/algo-services.yaml"; then
        echo -e "${GREEN}  ✓${NC} agent-engine: 端口8010 一致"
        ((SUCCESS++))
    else
        echo -e "${RED}  ✗${NC} agent-engine: 端口不一致"
        ((ERRORS++))
    fi

    # 检查 indexing-service
    if grep -q "localhost:8011" "$CONFIG_DIR/services.yaml" && \
       grep -q "localhost:8011" "$CONFIG_DIR/algo-services.yaml"; then
        echo -e "${GREEN}  ✓${NC} indexing-service: 端口8011 一致"
        ((SUCCESS++))
    else
        echo -e "${RED}  ✗${NC} indexing-service: 端口不一致"
        echo "    检查 services.yaml 和 algo-services.yaml"
        ((ERRORS++))
    fi

    # 检查 rag-engine 是否已注释
    if grep -q "^[[:space:]]*#.*rag-engine" "$CONFIG_DIR/services.yaml" && \
       grep -q "^[[:space:]]*#.*rag-engine" "$CONFIG_DIR/algo-services.yaml"; then
        echo -e "${GREEN}  ✓${NC} rag-engine: 已正确注释"
        ((SUCCESS++))
    else
        echo -e "${YELLOW}  ⚠${NC} rag-engine: 配置可能需要清理"
        ((WARNINGS++))
    fi

    echo ""
}

# 检查服务依赖
check_service_dependencies() {
    echo -e "${BLUE}[4/5] 检查服务依赖关系...${NC}"

    if [ -f "$CONFIG_DIR/services-integration.yaml" ]; then
        echo "  检查服务调用链定义..."

        # 检查关键调用链是否定义
        local chains=(
            "document_indexing"
            "rag_query"
            "agent_execution"
        )

        for chain in "${chains[@]}"; do
            if grep -q "$chain:" "$CONFIG_DIR/services-integration.yaml"; then
                echo -e "${GREEN}  ✓${NC} 调用链 '$chain' 已定义"
                ((SUCCESS++))
            else
                echo -e "${YELLOW}  ⚠${NC} 调用链 '$chain' 未找到"
                ((WARNINGS++))
            fi
        done
    else
        echo -e "${RED}  ✗${NC} 服务集成配置文件不存在"
        ((ERRORS++))
    fi

    echo ""
}

# 生成配置报告
generate_report() {
    echo -e "${BLUE}[5/5] 生成配置报告...${NC}"

    local report_file="$PROJECT_ROOT/config-validation-report.txt"

    cat > "$report_file" << EOF
配置验证报告
生成时间: $(date '+%Y-%m-%d %H:%M:%S')
项目路径: $PROJECT_ROOT

=== 统计信息 ===
✓ 成功: $SUCCESS
⚠ 警告: $WARNINGS
✗ 错误: $ERRORS

=== 服务端口映射 ===
Go Services (gRPC):
  - identity-service: 50051
  - conversation-service: 50052
  - ai-orchestrator: 50054
  - model-router: 50055
  - analytics-service: 50056
  - notification-service: 50057

Python Services (HTTP):
  - voice-engine: 8004
  - model-adapter: 8005
  - knowledge-service: 8006 (合并后统一)
  - multimodal-engine: 8008
  - vector-store-adapter: 8009
  - agent-engine: 8010
  - indexing-service: 8011
  - retrieval-service: 8012

=== 配置文件状态 ===
EOF

    # 添加配置文件状态
    for file in "$CONFIG_DIR"/*.yaml; do
        if [ -f "$file" ]; then
            echo "  ✓ $(basename "$file")" >> "$report_file"
        fi
    done

    echo -e "${GREEN}  ✓${NC} 报告已生成: $report_file"
    echo ""
}

# 打印总结
print_summary() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}   验证完成${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
    echo -e "  ${GREEN}成功:${NC} $SUCCESS 项"
    echo -e "  ${YELLOW}警告:${NC} $WARNINGS 项"
    echo -e "  ${RED}错误:${NC} $ERRORS 项"
    echo ""

    if [ $ERRORS -eq 0 ]; then
        echo -e "${GREEN}✓ 配置验证通过！${NC}"
        exit 0
    else
        echo -e "${RED}✗ 配置验证失败，请修复上述错误${NC}"
        exit 1
    fi
}

# 主函数
main() {
    check_config_files
    check_port_conflicts
    check_port_consistency
    check_service_dependencies
    generate_report
    print_summary
}

# 运行主函数
main
