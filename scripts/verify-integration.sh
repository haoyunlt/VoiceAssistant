#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper 服务集成验证脚本
# 用途: 验证各服务间的集成和连通性

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 计数器
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖工具..."

    local deps=("kubectl" "curl" "jq")
    for dep in "${deps[@]}"; do
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
        if command -v "$dep" &> /dev/null; then
            log_success "$dep 已安装"
        else
            log_fail "$dep 未安装"
        fi
    done
}

# 检查 Kubernetes 集群
check_k8s_cluster() {
    log_info "检查 Kubernetes 集群..."

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if kubectl cluster-info &> /dev/null; then
        log_success "Kubernetes 集群连接正常"
    else
        log_fail "无法连接到 Kubernetes 集群"
        return 1
    fi
}

# 检查命名空间
check_namespaces() {
    log_info "检查命名空间..."

    local namespaces=("voiceassistant-prod" "voiceassistant-infra" "istio-system")
    for ns in "${namespaces[@]}"; do
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
        if kubectl get namespace "$ns" &> /dev/null; then
            log_success "命名空间 $ns 存在"
        else
            log_fail "命名空间 $ns 不存在"
        fi
    done
}

# 检查基础设施服务
check_infrastructure() {
    log_info "检查基础设施服务..."

    local services=(
        "postgres:voiceassistant-infra"
        "redis:voiceassistant-infra"
        "nacos:voiceassistant-infra"
        "milvus:voiceassistant-infra"
    )

    for svc in "${services[@]}"; do
        IFS=':' read -r name namespace <<< "$svc"
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        local ready=$(kubectl get pods -n "$namespace" -l "app=$name" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

        if [ "$ready" = "True" ]; then
            log_success "$name 服务运行正常"
        else
            log_fail "$name 服务未就绪"
        fi
    done
}

# 检查 Go 服务
check_go_services() {
    log_info "检查 Go 服务..."

    local services=(
        "identity-service"
        "conversation-service"
        "knowledge-service"
        "ai-orchestrator"
        "model-router"
        "notification-service"
        "analytics-service"
    )

    for svc in "${services[@]}"; do
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        local ready=$(kubectl get pods -n voiceassistant-prod -l "app=$svc" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

        if [ "$ready" = "True" ]; then
            log_success "$svc 运行正常"
        else
            log_fail "$svc 未就绪"
        fi
    done
}

# 检查 Python AI 服务
check_python_services() {
    log_info "检查 Python AI 服务..."

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

    for svc in "${services[@]}"; do
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        local ready=$(kubectl get pods -n voiceassistant-prod -l "app=$svc" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

        if [ "$ready" = "True" ]; then
            log_success "$svc 运行正常"
        else
            log_fail "$svc 未就绪"
        fi
    done
}

# 检查 Istio 配置
check_istio() {
    log_info "检查 Istio 配置..."

    # 检查 Gateway
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if kubectl get gateway -n istio-system &> /dev/null; then
        log_success "Istio Gateway 已配置"
    else
        log_fail "Istio Gateway 未配置"
    fi

    # 检查 VirtualService
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local vs_count=$(kubectl get virtualservice -n voiceassistant-prod --no-headers 2>/dev/null | wc -l)
    if [ "$vs_count" -gt 0 ]; then
        log_success "VirtualService 已配置 ($vs_count 个)"
    else
        log_fail "VirtualService 未配置"
    fi

    # 检查 DestinationRule
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local dr_count=$(kubectl get destinationrule -n voiceassistant-prod --no-headers 2>/dev/null | wc -l)
    if [ "$dr_count" -gt 0 ]; then
        log_success "DestinationRule 已配置 ($dr_count 个)"
    else
        log_fail "DestinationRule 未配置"
    fi

    # 使用 istioctl 分析
    if command -v istioctl &> /dev/null; then
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
        if istioctl analyze -n voiceassistant-prod &> /dev/null; then
            log_success "Istio 配置验证通过"
        else
            log_warn "Istio 配置存在警告，运行 'istioctl analyze' 查看详情"
        fi
    fi
}

# 检查服务连通性
check_connectivity() {
    log_info "检查服务连通性..."

    # 获取 Ingress Gateway 地址
    local ingress_host=$(kubectl -n istio-system get service istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

    if [ -z "$ingress_host" ]; then
        log_warn "Ingress Gateway LoadBalancer IP 未分配，跳过连通性测试"
        return
    fi

    # 测试健康检查端点
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if curl -s -f "http://${ingress_host}/health" &> /dev/null; then
        log_success "Gateway 健康检查通过"
    else
        log_fail "Gateway 健康检查失败"
    fi
}

# 检查服务间通信（mTLS）
check_mtls() {
    log_info "检查 mTLS 配置..."

    if ! command -v istioctl &> /dev/null; then
        log_warn "istioctl 未安装，跳过 mTLS 检查"
        return
    fi

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if kubectl get peerauthentication -n voiceassistant-prod &> /dev/null; then
        log_success "mTLS PeerAuthentication 已配置"
    else
        log_fail "mTLS PeerAuthentication 未配置"
    fi
}

# 检查配置中心连接
check_nacos_connection() {
    log_info "检查 Nacos 配置中心连接..."

    # 获取 Nacos Pod
    local nacos_pod=$(kubectl get pod -n voiceassistant-infra -l app=nacos -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$nacos_pod" ]; then
        log_warn "未找到 Nacos Pod，跳过连接检查"
        return
    fi

    # 端口转发测试（临时）
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    kubectl port-forward -n voiceassistant-infra "$nacos_pod" 18848:8848 &> /dev/null &
    local pf_pid=$!
    sleep 2

    if curl -s -f "http://localhost:18848/nacos/v1/console/health" &> /dev/null; then
        log_success "Nacos 配置中心连接正常"
    else
        log_fail "Nacos 配置中心连接失败"
    fi

    kill "$pf_pid" 2>/dev/null || true
}

# 检查数据库连接
check_database_connections() {
    log_info "检查数据库连接..."

    # 检查 PostgreSQL
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local pg_pod=$(kubectl get pod -n voiceassistant-infra -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$pg_pod" ]; then
        if kubectl exec -n voiceassistant-infra "$pg_pod" -- psql -U voiceassistant -c "SELECT 1" &> /dev/null; then
            log_success "PostgreSQL 连接正常"
        else
            log_fail "PostgreSQL 连接失败"
        fi
    else
        log_fail "未找到 PostgreSQL Pod"
    fi

    # 检查 Redis
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local redis_pod=$(kubectl get pod -n voiceassistant-infra -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -n "$redis_pod" ]; then
        if kubectl exec -n voiceassistant-infra "$redis_pod" -- redis-cli ping 2>/dev/null | grep -q "PONG"; then
            log_success "Redis 连接正常"
        else
            log_fail "Redis 连接失败"
        fi
    else
        log_fail "未找到 Redis Pod"
    fi
}

# 检查 HPA 配置
check_hpa() {
    log_info "检查 HPA 自动扩缩容..."

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local hpa_count=$(kubectl get hpa -n voiceassistant-prod --no-headers 2>/dev/null | wc -l)

    if [ "$hpa_count" -gt 0 ]; then
        log_success "HPA 已配置 ($hpa_count 个)"
    else
        log_warn "未配置 HPA 自动扩缩容"
    fi
}

# 生成报告
generate_report() {
    echo ""
    log_info "========================================"
    log_info "验证报告"
    log_info "========================================"
    echo ""
    echo "总检查项: $TOTAL_CHECKS"
    echo -e "${GREEN}通过: $PASSED_CHECKS${NC}"
    echo -e "${RED}失败: $FAILED_CHECKS${NC}"
    echo ""

    local success_rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED_CHECKS/$TOTAL_CHECKS)*100}")
    echo "成功率: ${success_rate}%"
    echo ""

    if [ "$FAILED_CHECKS" -eq 0 ]; then
        log_success "所有检查通过！系统运行正常"
        return 0
    else
        log_warn "部分检查失败，请查看上述详情"
        return 1
    fi
}

# 主函数
main() {
    echo ""
    log_info "========================================"
    log_info "VoiceHelper 服务集成验证"
    log_info "========================================"
    echo ""

    check_dependencies
    echo ""

    check_k8s_cluster || exit 1
    echo ""

    check_namespaces
    echo ""

    check_infrastructure
    echo ""

    check_go_services
    echo ""

    check_python_services
    echo ""

    check_istio
    echo ""

    check_connectivity
    echo ""

    check_mtls
    echo ""

    check_nacos_connection
    echo ""

    check_database_connections
    echo ""

    check_hpa
    echo ""

    generate_report
}

# 执行主函数
main "$@"
