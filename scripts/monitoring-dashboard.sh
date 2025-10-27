#!/usr/bin/env bash
set -euo pipefail

# 监控面板一键访问脚本

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

# 启动Grafana
start_grafana() {
    log_info "启动 Grafana..."
    if ! check_port 3000; then
        log_warn "端口 3000 已被占用"
        return
    fi
    kubectl port-forward -n istio-system svc/grafana 3000:3000 &
    echo "Grafana: http://localhost:3000"
}

# 启动Kiali
start_kiali() {
    log_info "启动 Kiali..."
    if ! check_port 20001; then
        log_warn "端口 20001 已被占用"
        return
    fi
    kubectl port-forward -n istio-system svc/kiali 20001:20001 &
    echo "Kiali: http://localhost:20001"
}

# 启动Jaeger
start_jaeger() {
    log_info "启动 Jaeger..."
    if ! check_port 16686; then
        log_warn "端口 16686 已被占用"
        return
    fi
    kubectl port-forward -n istio-system svc/tracing 16686:16686 &
    echo "Jaeger: http://localhost:16686"
}

# 启动Prometheus
start_prometheus() {
    log_info "启动 Prometheus..."
    if ! check_port 9090; then
        log_warn "端口 9090 已被占用"
        return
    fi
    kubectl port-forward -n istio-system svc/prometheus 9090:9090 &
    echo "Prometheus: http://localhost:9090"
}

# 启动Nacos
start_nacos() {
    log_info "启动 Nacos..."
    if ! check_port 8848; then
        log_warn "端口 8848 已被占用"
        return
    fi
    kubectl port-forward -n voiceassistant-infra svc/nacos 8848:8848 &
    echo "Nacos: http://localhost:8848/nacos (nacos/nacos)"
}

# 停止所有端口转发
stop_all() {
    log_info "停止所有端口转发..."
    pkill -f "kubectl port-forward" || true
    log_info "已停止"
}

# 显示帮助
show_help() {
    cat << EOF
监控面板访问脚本

用法: $0 [选项]

选项:
    all         启动所有监控面板
    grafana     启动 Grafana
    kiali       启动 Kiali
    jaeger      启动 Jaeger
    prometheus  启动 Prometheus
    nacos       启动 Nacos
    stop        停止所有端口转发
    help        显示帮助信息

示例:
    $0 all          # 启动所有面板
    $0 grafana      # 只启动Grafana
    $0 stop         # 停止所有
EOF
}

# 主函数
main() {
    case "${1:-all}" in
        all)
            start_grafana
            sleep 1
            start_kiali
            sleep 1
            start_jaeger
            sleep 1
            start_prometheus
            sleep 1
            start_nacos

            echo ""
            log_info "所有监控面板已启动"
            log_info "按 Ctrl+C 停止所有端口转发"
            wait
            ;;
        grafana)
            start_grafana
            wait
            ;;
        kiali)
            start_kiali
            wait
            ;;
        jaeger)
            start_jaeger
            wait
            ;;
        prometheus)
            start_prometheus
            wait
            ;;
        nacos)
            start_nacos
            wait
            ;;
        stop)
            stop_all
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_warn "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
}

# 捕获退出信号
trap stop_all EXIT INT TERM

main "$@"
