#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper 监控面板启动脚本
# 用途: 一键启动 Grafana/Prometheus/Jaeger/Kiali/Nacos 监控面板

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 kubectl
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到 Kubernetes 集群"
        exit 1
    fi
}

# 检查 Pod 是否就绪
check_pod_ready() {
    local namespace=$1
    local selector=$2
    local service_name=$3

    if kubectl get pods -n "$namespace" -l "$selector" &> /dev/null; then
        local ready=$(kubectl get pods -n "$namespace" -l "$selector" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
        if [ "$ready" = "True" ]; then
            return 0
        fi
    fi

    log_warn "${service_name} Pod 未就绪，跳过"
    return 1
}

# 启动 Grafana
start_grafana() {
    log_info "启动 Grafana 面板..."

    if ! check_pod_ready "voiceassistant-infra" "app=grafana" "Grafana"; then
        return 1
    fi

    # 查找 Grafana Pod
    local grafana_pod=$(kubectl get pod -n voiceassistant-infra -l app=grafana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$grafana_pod" ]; then
        log_error "未找到 Grafana Pod"
        return 1
    fi

    log_success "Grafana 面板启动中..."
    echo "  访问地址: http://localhost:3000"
    echo "  默认账号: admin / admin"

    kubectl port-forward -n voiceassistant-infra "$grafana_pod" 3000:3000 &
    local pid=$!
    echo "$pid" >> /tmp/voicehelper-monitoring-pids.txt

    sleep 2
    log_success "Grafana 已启动 (PID: $pid)"
}

# 启动 Prometheus
start_prometheus() {
    log_info "启动 Prometheus 面板..."

    if ! check_pod_ready "voiceassistant-infra" "app=prometheus" "Prometheus"; then
        return 1
    fi

    local prometheus_pod=$(kubectl get pod -n voiceassistant-infra -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$prometheus_pod" ]; then
        log_error "未找到 Prometheus Pod"
        return 1
    fi

    log_success "Prometheus 面板启动中..."
    echo "  访问地址: http://localhost:9090"

    kubectl port-forward -n voiceassistant-infra "$prometheus_pod" 9090:9090 &
    local pid=$!
    echo "$pid" >> /tmp/voicehelper-monitoring-pids.txt

    sleep 2
    log_success "Prometheus 已启动 (PID: $pid)"
}

# 启动 Jaeger
start_jaeger() {
    log_info "启动 Jaeger 面板..."

    if ! check_pod_ready "voiceassistant-infra" "app=jaeger" "Jaeger"; then
        return 1
    fi

    local jaeger_pod=$(kubectl get pod -n voiceassistant-infra -l app=jaeger -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$jaeger_pod" ]; then
        log_error "未找到 Jaeger Pod"
        return 1
    fi

    log_success "Jaeger 面板启动中..."
    echo "  访问地址: http://localhost:16686"

    kubectl port-forward -n voiceassistant-infra "$jaeger_pod" 16686:16686 &
    local pid=$!
    echo "$pid" >> /tmp/voicehelper-monitoring-pids.txt

    sleep 2
    log_success "Jaeger 已启动 (PID: $pid)"
}

# 启动 Kiali
start_kiali() {
    log_info "启动 Kiali 面板..."

    # Kiali 通常在 istio-system 命名空间
    if ! kubectl get namespace istio-system &> /dev/null; then
        log_warn "istio-system 命名空间不存在，跳过 Kiali"
        return 1
    fi

    if ! check_pod_ready "istio-system" "app=kiali" "Kiali"; then
        log_warn "Kiali 未安装，使用 istioctl dashboard kiali 手动启动"
        return 1
    fi

    local kiali_pod=$(kubectl get pod -n istio-system -l app=kiali -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$kiali_pod" ]; then
        log_warn "未找到 Kiali Pod"
        return 1
    fi

    log_success "Kiali 面板启动中..."
    echo "  访问地址: http://localhost:20001"

    kubectl port-forward -n istio-system "$kiali_pod" 20001:20001 &
    local pid=$!
    echo "$pid" >> /tmp/voicehelper-monitoring-pids.txt

    sleep 2
    log_success "Kiali 已启动 (PID: $pid)"
}

# 启动 Nacos
start_nacos() {
    log_info "启动 Nacos 面板..."

    if ! check_pod_ready "voiceassistant-infra" "app=nacos" "Nacos"; then
        return 1
    fi

    local nacos_pod=$(kubectl get pod -n voiceassistant-infra -l app=nacos -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$nacos_pod" ]; then
        log_error "未找到 Nacos Pod"
        return 1
    fi

    log_success "Nacos 面板启动中..."
    echo "  访问地址: http://localhost:8848/nacos"
    echo "  默认账号: nacos / nacos"

    kubectl port-forward -n voiceassistant-infra "$nacos_pod" 8848:8848 &
    local pid=$!
    echo "$pid" >> /tmp/voicehelper-monitoring-pids.txt

    sleep 2
    log_success "Nacos 已启动 (PID: $pid)"
}

# 启动所有面板
start_all() {
    log_info "启动所有监控面板..."
    echo ""

    start_grafana || true
    echo ""
    start_prometheus || true
    echo ""
    start_jaeger || true
    echo ""
    start_kiali || true
    echo ""
    start_nacos || true
    echo ""

    show_summary
}

# 停止所有面板
stop_all() {
    log_info "停止所有监控面板..."

    if [ -f /tmp/voicehelper-monitoring-pids.txt ]; then
        while read -r pid; do
            if ps -p "$pid" > /dev/null 2>&1; then
                log_info "停止进程: $pid"
                kill "$pid" 2>/dev/null || true
            fi
        done < /tmp/voicehelper-monitoring-pids.txt

        rm -f /tmp/voicehelper-monitoring-pids.txt
        log_success "所有监控面板已停止"
    else
        log_warn "未找到运行中的监控面板"
    fi
}

# 显示摘要信息
show_summary() {
    echo ""
    log_info "========================================"
    log_info "监控面板已启动"
    log_info "========================================"
    echo ""
    echo "📊 Grafana:    http://localhost:3000    (admin/admin)"
    echo "📈 Prometheus: http://localhost:9090"
    echo "🔍 Jaeger:     http://localhost:16686"
    echo "🕸️  Kiali:      http://localhost:20001"
    echo "⚙️  Nacos:      http://localhost:8848/nacos (nacos/nacos)"
    echo ""
    log_info "停止所有面板: $0 stop"
    log_info "查看运行状态: $0 status"
    echo ""
    log_warn "提示: 按 Ctrl+C 不会停止后台进程，请使用 '$0 stop' 停止"
}

# 显示运行状态
show_status() {
    log_info "检查监控面板状态..."
    echo ""

    if [ ! -f /tmp/voicehelper-monitoring-pids.txt ]; then
        log_warn "没有运行中的监控面板"
        return
    fi

    local running=0
    while read -r pid; do
        if ps -p "$pid" > /dev/null 2>&1; then
            local cmd=$(ps -p "$pid" -o args= | head -c 50)
            log_success "运行中: PID=$pid, CMD=$cmd..."
            running=$((running + 1))
        fi
    done < /tmp/voicehelper-monitoring-pids.txt

    echo ""
    if [ $running -gt 0 ]; then
        log_success "共 $running 个监控面板运行中"
    else
        log_warn "没有运行中的监控面板"
        rm -f /tmp/voicehelper-monitoring-pids.txt
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
VoiceHelper 监控面板启动脚本

用法: $0 <命令>

命令:
  all          启动所有监控面板
  grafana      启动 Grafana
  prometheus   启动 Prometheus
  jaeger       启动 Jaeger
  kiali        启动 Kiali
  nacos        启动 Nacos
  stop         停止所有监控面板
  status       查看运行状态
  -h, --help   显示帮助信息

示例:
  $0 all          # 启动所有面板
  $0 grafana      # 仅启动 Grafana
  $0 stop         # 停止所有面板
  $0 status       # 查看状态

注意:
  - 面板会在后台运行
  - 使用 'stop' 命令停止所有面板
  - 确保对应服务已部署到 K8s 集群

EOF
}

# 主函数
main() {
    # 检查 kubectl
    check_kubectl

    # 清理旧的 PID 文件
    if [ -f /tmp/voicehelper-monitoring-pids.txt ]; then
        while read -r pid; do
            if ! ps -p "$pid" > /dev/null 2>&1; then
                sed -i.bak "/^$pid$/d" /tmp/voicehelper-monitoring-pids.txt 2>/dev/null || true
            fi
        done < /tmp/voicehelper-monitoring-pids.txt
    fi

    # 解析命令
    case "${1:-all}" in
        all)
            start_all
            ;;
        grafana)
            start_grafana
            ;;
        prometheus)
            start_prometheus
            ;;
        jaeger)
            start_jaeger
            ;;
        kiali)
            start_kiali
            ;;
        nacos)
            start_nacos
            ;;
        stop)
            stop_all
            ;;
        status)
            show_status
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
