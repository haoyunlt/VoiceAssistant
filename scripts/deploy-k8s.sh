#!/usr/bin/env bash
set -euo pipefail

# VoiceAssistant Kubernetes + Istio 部署脚本
# 用途：一键部署所有服务到 Kubernetes 集群

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYMENTS_DIR="${PROJECT_ROOT}/deployments/k8s"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1\n"
}

# 检查依赖
check_dependencies() {
    log_step "检查依赖工具..."

    local deps=("kubectl" "helm" "istioctl")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "$dep 未安装，请先安装"
            exit 1
        else
            log_info "✓ $dep 已安装"
        fi
    done
}

# 检查Kubernetes集群连接
check_cluster() {
    log_step "检查 Kubernetes 集群连接..."

    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到 Kubernetes 集群"
        exit 1
    fi

    log_info "✓ 集群连接正常"
    kubectl cluster-info | head -n 1
}

# 安装 Istio
install_istio() {
    log_step "安装 Istio..."

    if kubectl get namespace istio-system &> /dev/null; then
        log_warn "Istio 命名空间已存在，跳过安装"
        return
    fi

    log_info "使用 istioctl 安装 Istio..."
    istioctl install --set profile=production -y

    # 安装监控组件
    log_info "安装 Istio 监控组件..."
    kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/prometheus.yaml || true
    kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/grafana.yaml || true
    kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/jaeger.yaml || true
    kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/kiali.yaml || true

    log_info "✓ Istio 安装完成"
}

# 创建命名空间和基础配置
deploy_base() {
    log_step "部署基础配置..."

    kubectl apply -f "${DEPLOYMENTS_DIR}/deploy-all.yaml"

    # 创建Istio命名空间
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/namespace.yaml"

    log_info "✓ 基础配置部署完成"
}

# 部署基础设施服务
deploy_infrastructure() {
    log_step "部署基础设施服务..."

    log_info "部署 PostgreSQL..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/infrastructure/postgres.yaml"

    log_info "部署 Redis..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/infrastructure/redis.yaml"

    log_info "部署 Nacos..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/infrastructure/nacos.yaml"

    log_info "部署 Milvus..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/infrastructure/milvus.yaml"

    log_info "部署 Elasticsearch..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/infrastructure/elasticsearch.yaml"

    log_info "✓ 基础设施服务部署完成"

    # 等待基础设施服务就绪
    log_info "等待基础设施服务就绪..."
    kubectl wait --for=condition=ready pod -l app=postgres -n voiceassistant-infra --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=redis -n voiceassistant-infra --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=nacos -n voiceassistant-infra --timeout=300s || true
}

# 部署Istio配置
deploy_istio_config() {
    log_step "部署 Istio 配置..."

    log_info "部署 Gateway..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/gateway.yaml"

    log_info "部署 VirtualService..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/virtual-service.yaml"

    log_info "部署 DestinationRule..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/destination-rule.yaml"

    log_info "部署 Security 配置..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/security.yaml"

    log_info "部署 Telemetry 配置..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/telemetry.yaml"

    log_info "部署 Traffic Management 配置..."
    kubectl apply -f "${DEPLOYMENTS_DIR}/istio/traffic-management.yaml"

    log_info "✓ Istio 配置部署完成"
}

# 部署Go服务
deploy_go_services() {
    log_step "部署 Go 服务..."

    local services=(
        "identity-service"
        "conversation-service"
        "knowledge-service"
        "ai-orchestrator"
        "notification-service"
        "analytics-service"
    )

    for service in "${services[@]}"; do
        log_info "部署 ${service}..."
        kubectl apply -f "${DEPLOYMENTS_DIR}/services/go/${service}.yaml"
    done

    log_info "✓ Go 服务部署完成"
}

# 部署Python服务
deploy_python_services() {
    log_step "部署 Python 服务..."

    local services=(
        "agent-engine"
        "rag-engine"
        "voice-engine"
        "model-adapter"
        "retrieval-service"
        "indexing-service"
        "multimodal-engine"
        "vector-store-adapter"
    )

    for service in "${services[@]}"; do
        log_info "部署 ${service}..."
        kubectl apply -f "${DEPLOYMENTS_DIR}/services/python/${service}.yaml"
    done

    log_info "✓ Python 服务部署完成"
}

# 验证部署
verify_deployment() {
    log_step "验证部署状态..."

    log_info "检查命名空间..."
    kubectl get namespaces | grep voiceassistant

    log_info "\n检查基础设施服务..."
    kubectl get pods -n voiceassistant-infra

    log_info "\n检查应用服务..."
    kubectl get pods -n voiceassistant-prod

    log_info "\n检查 Istio Gateway..."
    kubectl get gateway -n voiceassistant-prod

    log_info "\n检查 Services..."
    kubectl get svc -n voiceassistant-prod

    log_info "\n检查 HPA..."
    kubectl get hpa -n voiceassistant-prod

    log_info "\n✓ 部署验证完成"
}

# 显示访问信息
show_access_info() {
    log_step "访问信息"

    log_info "获取 Istio Ingress Gateway 地址..."
    INGRESS_HOST=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    INGRESS_PORT=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.spec.ports[?(@.name=="http2")].port}')
    SECURE_INGRESS_PORT=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.spec.ports[?(@.name=="https")].port}')

    echo ""
    log_info "========== 访问地址 =========="
    echo "API Gateway: http://${INGRESS_HOST}:${INGRESS_PORT}"
    echo "API Gateway (HTTPS): https://${INGRESS_HOST}:${SECURE_INGRESS_PORT}"
    echo ""

    log_info "========== 监控面板 =========="
    echo "Grafana: kubectl port-forward -n istio-system svc/grafana 3000:3000"
    echo "Kiali: kubectl port-forward -n istio-system svc/kiali 20001:20001"
    echo "Jaeger: kubectl port-forward -n istio-system svc/tracing 16686:16686"
    echo "Prometheus: kubectl port-forward -n istio-system svc/prometheus 9090:9090"
    echo ""

    log_info "========== Nacos 控制台 =========="
    echo "Nacos: kubectl port-forward -n voiceassistant-infra svc/nacos 8848:8848"
    echo "访问: http://localhost:8848/nacos (用户名/密码: nacos/nacos)"
    echo ""
}

# 主函数
main() {
    log_info "VoiceAssistant Kubernetes + Istio 部署脚本"
    log_info "==========================================="

    # 解析参数
    SKIP_ISTIO=false
    SKIP_INFRA=false
    VERIFY_ONLY=false

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
            --verify-only)
                VERIFY_ONLY=true
                shift
                ;;
            *)
                log_error "未知参数: $1"
                echo "用法: $0 [--skip-istio] [--skip-infra] [--verify-only]"
                exit 1
                ;;
        esac
    done

    # 检查依赖
    check_dependencies
    check_cluster

    if [ "$VERIFY_ONLY" = true ]; then
        verify_deployment
        exit 0
    fi

    # 执行部署
    if [ "$SKIP_ISTIO" = false ]; then
        install_istio
    else
        log_warn "跳过 Istio 安装"
    fi

    deploy_base

    if [ "$SKIP_INFRA" = false ]; then
        deploy_infrastructure
    else
        log_warn "跳过基础设施服务部署"
    fi

    deploy_istio_config
    deploy_go_services
    deploy_python_services

    # 验证部署
    verify_deployment

    # 显示访问信息
    show_access_info

    log_info "\n${GREEN}✓ 部署完成！${NC}"
}

# 执行主函数
main "$@"
