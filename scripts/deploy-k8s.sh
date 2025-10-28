#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper Kubernetes 一键部署脚本
# 用途: 自动部署所有服务到 Kubernetes 集群

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
K8S_DIR="${PROJECT_ROOT}/deployments/k8s"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 未安装，请先安装 $1"
        exit 1
    fi
}

# 检查依赖工具
check_dependencies() {
    log_info "检查依赖工具..."
    check_command kubectl
    check_command helm

    # istioctl 可选
    if ! command -v istioctl &> /dev/null; then
        log_warn "istioctl 未安装，将跳过 Istio 安装"
        SKIP_ISTIO=true
    fi

    log_success "依赖工具检查完成"
}

# 检查 Kubernetes 连接
check_k8s_connection() {
    log_info "检查 Kubernetes 连接..."
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到 Kubernetes 集群"
        log_error "请确保 kubectl 已正确配置"
        exit 1
    fi

    local context=$(kubectl config current-context)
    log_success "已连接到 Kubernetes 集群: ${context}"
}

# 安装 Istio
install_istio() {
    if [ "${SKIP_ISTIO:-false}" = "true" ]; then
        log_info "跳过 Istio 安装"
        return
    fi

    log_info "检查 Istio 安装状态..."

    if kubectl get namespace istio-system &> /dev/null; then
        log_info "Istio 已安装，跳过安装步骤"
        return
    fi

    log_info "安装 Istio (production profile)..."
    istioctl install --set profile=production -y

    log_info "等待 Istio 就绪..."
    kubectl wait --for=condition=ready pod -l app=istiod -n istio-system --timeout=300s
    kubectl wait --for=condition=ready pod -l app=istio-ingressgateway -n istio-system --timeout=300s

    log_success "Istio 安装完成"
}

# 创建命名空间
create_namespaces() {
    log_info "创建命名空间..."

    kubectl apply -f "${K8S_DIR}/istio/namespace.yaml"

    # 标记应用命名空间启用 Istio 注入
    kubectl label namespace voiceassistant-prod istio-injection=enabled --overwrite

    log_success "命名空间创建完成"
}

# 部署基础设施
deploy_infrastructure() {
    if [ "${SKIP_INFRA:-false}" = "true" ]; then
        log_info "跳过基础设施部署"
        return
    fi

    log_info "部署基础设施服务..."

    # 核心存储
    log_info "部署 PostgreSQL..."
    kubectl apply -f "${K8S_DIR}/infrastructure/postgres.yaml"

    log_info "部署 Redis..."
    kubectl apply -f "${K8S_DIR}/infrastructure/redis.yaml"

    log_info "部署 Nacos..."
    kubectl apply -f "${K8S_DIR}/infrastructure/nacos.yaml"

    log_info "部署 Milvus..."
    kubectl apply -f "${K8S_DIR}/infrastructure/milvus.yaml"

    # 可选服务
    if [ "${DEPLOY_FULL:-true}" = "true" ]; then
        log_info "部署 Elasticsearch..."
        kubectl apply -f "${K8S_DIR}/infrastructure/elasticsearch.yaml"

        log_info "部署 ClickHouse..."
        kubectl apply -f "${K8S_DIR}/infrastructure/clickhouse.yaml"

        log_info "部署 Kafka..."
        kubectl apply -f "${K8S_DIR}/infrastructure/kafka.yaml"

        log_info "部署 MinIO..."
        kubectl apply -f "${K8S_DIR}/infrastructure/minio-standalone.yaml"
    fi

    log_info "等待核心基础设施就绪..."
    kubectl wait --for=condition=ready pod -l app=postgres -n voiceassistant-infra --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=redis -n voiceassistant-infra --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=nacos -n voiceassistant-infra --timeout=300s || true

    log_success "基础设施部署完成"
}

# 部署监控服务
deploy_monitoring() {
    if [ "${SKIP_MONITORING:-false}" = "true" ]; then
        log_info "跳过监控服务部署"
        return
    fi

    log_info "部署监控服务..."

    kubectl apply -f "${K8S_DIR}/infrastructure/prometheus-grafana.yaml"
    kubectl apply -f "${K8S_DIR}/infrastructure/jaeger.yaml"
    kubectl apply -f "${K8S_DIR}/infrastructure/alertmanager.yaml"

    log_success "监控服务部署完成"
}

# 配置 Istio
configure_istio() {
    log_info "配置 Istio..."

    kubectl apply -f "${K8S_DIR}/istio/gateway.yaml"
    kubectl apply -f "${K8S_DIR}/istio/virtual-service.yaml"
    kubectl apply -f "${K8S_DIR}/istio/destination-rule.yaml"
    kubectl apply -f "${K8S_DIR}/istio/security.yaml"
    kubectl apply -f "${K8S_DIR}/istio/telemetry.yaml"
    kubectl apply -f "${K8S_DIR}/istio/envoy-filter.yaml"

    log_success "Istio 配置完成"
}

# 部署应用服务
deploy_services() {
    log_info "部署应用服务..."

    # Go 服务
    log_info "部署 Go 服务..."
    kubectl apply -f "${K8S_DIR}/services/go/identity-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/go/conversation-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/go/knowledge-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/go/ai-orchestrator.yaml"
    kubectl apply -f "${K8S_DIR}/services/go/notification-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/go/analytics-service.yaml"

    # Python AI 服务
    log_info "部署 Python AI 服务..."
    kubectl apply -f "${K8S_DIR}/services/python/agent-engine.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/rag-engine.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/voice-engine.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/model-adapter.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/retrieval-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/indexing-service.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/multimodal-engine.yaml"
    kubectl apply -f "${K8S_DIR}/services/python/vector-store-adapter.yaml"

    log_success "应用服务部署完成"
}

# 验证部署
verify_deployment() {
    if [ "${VERIFY_ONLY:-false}" = "true" ]; then
        log_info "执行部署验证..."
    else
        log_info "验证部署状态..."
    fi

    # 检查 Pod 状态
    log_info "检查应用 Pod 状态..."
    kubectl get pods -n voiceassistant-prod

    log_info "检查基础设施 Pod 状态..."
    kubectl get pods -n voiceassistant-infra

    # 检查 Istio 配置
    log_info "验证 Istio 配置..."
    if command -v istioctl &> /dev/null; then
        istioctl analyze -n voiceassistant-prod
    fi

    # 获取 Gateway 地址
    log_info "获取 Ingress Gateway 地址..."
    local ingress_host=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")

    if [ "$ingress_host" != "pending" ] && [ -n "$ingress_host" ]; then
        log_success "Ingress Gateway 地址: http://${ingress_host}"
        log_info "测试健康检查: curl http://${ingress_host}/health"
    else
        log_warn "Ingress Gateway LoadBalancer IP 尚未分配"
        log_info "使用以下命令查看: kubectl get svc istio-ingressgateway -n istio-system"
    fi

    log_success "部署验证完成"
}

# 显示部署信息
show_deployment_info() {
    echo ""
    log_info "========================================"
    log_info "VoiceHelper 部署完成！"
    log_info "========================================"
    echo ""
    log_info "查看服务状态:"
    echo "  kubectl get all -n voiceassistant-prod"
    echo "  kubectl get all -n voiceassistant-infra"
    echo ""
    log_info "访问监控面板:"
    echo "  ./scripts/monitoring-dashboard.sh all"
    echo ""
    log_info "查看日志:"
    echo "  kubectl logs -n voiceassistant-prod -l app=<service-name> --tail=100 -f"
    echo ""
    log_info "详细文档:"
    echo "  deployments/k8s/README.md"
    echo "  docs/runbook/index.md"
    echo ""
}

# 显示帮助信息
show_help() {
    cat << EOF
VoiceHelper Kubernetes 一键部署脚本

用法: $0 [选项]

选项:
  --skip-istio         跳过 Istio 安装
  --skip-infra         跳过基础设施部署
  --skip-monitoring    跳过监控服务部署
  --minimal            最小化部署（仅核心服务）
  --verify-only        仅验证部署状态
  -h, --help           显示帮助信息

示例:
  $0                              # 完整部署
  $0 --skip-istio                 # 跳过 Istio 安装
  $0 --skip-infra                 # 跳过基础设施（假设已部署）
  $0 --minimal                    # 最小化部署
  $0 --verify-only                # 仅验证部署

EOF
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-istio)
                SKIP_ISTIO=true
                shift
                ;;
            --skip-infra)
                SKIP_INFRA=true
                shift
                ;;
            --skip-monitoring)
                SKIP_MONITORING=true
                shift
                ;;
            --minimal)
                DEPLOY_FULL=false
                SKIP_MONITORING=true
                shift
                ;;
            --verify-only)
                VERIFY_ONLY=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    log_info "========================================"
    log_info "VoiceHelper K8s 部署脚本"
    log_info "========================================"
    echo ""

    # 检查依赖
    check_dependencies
    check_k8s_connection

    # 仅验证模式
    if [ "${VERIFY_ONLY:-false}" = "true" ]; then
        verify_deployment
        exit 0
    fi

    # 执行部署
    install_istio
    create_namespaces
    deploy_infrastructure
    deploy_monitoring
    configure_istio
    deploy_services

    # 等待服务启动
    log_info "等待服务启动（可能需要 3-5 分钟）..."
    sleep 10

    # 验证部署
    verify_deployment

    # 显示部署信息
    show_deployment_info

    log_success "部署完成！"
}

# 执行主函数
main "$@"
