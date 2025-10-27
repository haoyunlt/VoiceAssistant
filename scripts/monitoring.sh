#!/bin/bash

# 监控栈管理脚本
# 用于启动、停止和管理 Docker Compose 监控服务

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMPOSE_FILE="docker-compose.monitoring.yml"

# 显示帮助
show_help() {
    cat << EOF
监控栈管理脚本

用法: $0 <command>

命令:
    start       启动监控服务
    stop        停止监控服务
    restart     重启监控服务
    status      查看服务状态
    logs        查看服务日志
    clean       停止并删除所有数据
    help        显示帮助信息

示例:
    $0 start            # 启动所有监控服务
    $0 stop             # 停止所有监控服务
    $0 logs grafana     # 查看 Grafana 日志
EOF
}

# 检查 Docker
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker 未运行，请先启动 Docker${NC}"
        exit 1
    fi
}

# 检查 docker-compose
check_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ docker-compose 未安装${NC}"
        exit 1
    fi

    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ 找不到 $COMPOSE_FILE${NC}"
        exit 1
    fi
}

# 启动监控服务
start_monitoring() {
    echo -e "${BLUE}🚀 启动 VoiceAssistant 监控栈...${NC}"
    echo ""

    check_docker
    check_compose

    echo "📊 启动监控服务..."
    docker-compose -f "$COMPOSE_FILE" up -d

    echo ""
    echo "⏳ 等待服务就绪..."
    sleep 10

    # 检查服务健康状态
    echo ""
    echo "🔍 检查服务健康状态..."

    # Check Prometheus
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Prometheus is running"
    else
        echo -e "  ${YELLOW}⚠${NC}  Prometheus may not be ready yet"
    fi

    # Check Grafana
    if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Grafana is running"
    else
        echo -e "  ${YELLOW}⚠${NC}  Grafana may not be ready yet"
    fi

    # Check Jaeger
    if curl -s http://localhost:16686 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Jaeger is running"
    else
        echo -e "  ${YELLOW}⚠${NC}  Jaeger may not be ready yet"
    fi

    echo ""
    echo -e "${GREEN}✅ 监控栈启动成功！${NC}"
    echo ""
    echo "📊 访问地址:"
    echo "  Prometheus:   http://localhost:9090"
    echo "  Grafana:      http://localhost:3001 (admin/admin)"
    echo "  Jaeger:       http://localhost:16686"
    echo "  AlertManager: http://localhost:9093"
    echo ""
    echo "📝 下一步:"
    echo "  1. 访问 Grafana 查看仪表盘"
    echo "  2. 配置 AlertManager 通知"
    echo "  3. 启动服务以查看指标"
    echo ""
}

# 停止监控服务
stop_monitoring() {
    echo -e "${BLUE}🛑 停止 VoiceAssistant 监控栈...${NC}"

    check_compose

    docker-compose -f "$COMPOSE_FILE" down

    echo -e "${GREEN}✅ 监控栈已停止${NC}"
    echo ""
    echo "💡 提示:"
    echo "  - 使用 '$0 start' 重新启动"
    echo "  - 使用 '$0 clean' 删除所有数据"
}

# 重启监控服务
restart_monitoring() {
    stop_monitoring
    echo ""
    start_monitoring
}

# 查看服务状态
show_status() {
    echo -e "${BLUE}📊 监控服务状态${NC}"
    echo ""

    check_compose
    docker-compose -f "$COMPOSE_FILE" ps
}

# 查看日志
show_logs() {
    check_compose

    if [ -n "$1" ]; then
        docker-compose -f "$COMPOSE_FILE" logs -f "$1"
    else
        docker-compose -f "$COMPOSE_FILE" logs -f
    fi
}

# 清理所有数据
clean_all() {
    echo -e "${RED}🗑️  清理监控数据（所有数据将被删除）${NC}"
    echo ""
    read -p "确认要删除所有监控数据吗? [y/N] " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        check_compose
        docker-compose -f "$COMPOSE_FILE" down -v
        echo -e "${GREEN}✅ 所有监控数据已清理${NC}"
    else
        echo "取消操作"
    fi
}

# 主函数
case "${1:-help}" in
    start)
        start_monitoring
        ;;
    stop)
        stop_monitoring
        ;;
    restart)
        restart_monitoring
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    clean)
        clean_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
