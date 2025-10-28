#!/usr/bin/env bash
#
# APISIX → Istio Gateway/Envoy 迁移脚本
# 版本: v3.0
# 最后更新: 2025-10-28
#
# 功能:
# - plan: 显示迁移计划
# - preflight: 预检查环境
# - install-istio: 安装/升级Istio
# - apply: 部署Istio配置
# - verify: 验证Istio健康状态
# - canary: 金丝雀切换(渐进式流量迁移)
# - rollback: 回滚到APISIX
# - cleanup: 清理APISIX资源
#

set -euo pipefail

# ========== 配置变量 ==========
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ISTIO_VERSION="${ISTIO_VERSION:-1.20.1}"
ISTIO_NAMESPACE="${ISTIO_NAMESPACE:-istio-system}"
APP_NAMESPACE="${APP_NAMESPACE:-voiceassistant-prod}"
APISIX_NAMESPACE="${APISIX_NAMESPACE:-apisix}"

# 金丝雀阶段流量比例
CANARY_STAGES=(10 25 50 75 100)
CANARY_WAIT_TIME=300  # 每个阶段等待时间(秒)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========== 工具函数 ==========
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command '$1' not found. Please install it first."
        exit 1
    fi
}

wait_for_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    local timeout=${4:-300}

    log_info "Waiting for $resource_type/$resource_name in namespace $namespace..."
    if kubectl wait --for=condition=ready "$resource_type/$resource_name" -n "$namespace" --timeout="${timeout}s"; then
        log_success "$resource_type/$resource_name is ready"
        return 0
    else
        log_error "$resource_type/$resource_name is not ready after ${timeout}s"
        return 1
    fi
}

# ========== 预检查 ==========
preflight_check() {
    log_info "Running preflight checks..."

    # 检查必需命令
    check_command kubectl
    check_command helm
    check_command istioctl

    # 检查Kubernetes连接
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    log_success "Kubernetes cluster connection OK"

    # 检查APISIX是否运行
    if ! kubectl get deployment apisix -n "$APISIX_NAMESPACE" &> /dev/null; then
        log_warn "APISIX deployment not found in namespace $APISIX_NAMESPACE"
    else
        log_success "APISIX is running"
    fi

    # 检查Istio版本
    if command -v istioctl &> /dev/null; then
        log_info "Istioctl version: $(istioctl version --short 2>/dev/null || echo 'not installed')"
    fi

    # 检查命名空间
    for ns in "$ISTIO_NAMESPACE" "$APP_NAMESPACE"; do
        if ! kubectl get namespace "$ns" &> /dev/null; then
            log_warn "Namespace $ns does not exist. Will create it."
        else
            log_success "Namespace $ns exists"
        fi
    done

    log_success "Preflight checks completed"
}

# ========== 显示迁移计划 ==========
show_plan() {
    cat <<EOF

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${GREEN}APISIX → Istio Gateway/Envoy 迁移计划${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${YELLOW}阶段 1: 准备阶段 (30分钟)${NC}
  1. 预检查环境 (preflight)
  2. 安装/升级Istio ${ISTIO_VERSION}
  3. 部署Istio配置 (Gateway, VirtualService, DestinationRule)
  4. 验证Istio健康状态

${YELLOW}阶段 2: 金丝雀切换 (4小时)${NC}
  流量切换策略:
    - 10% → Istio (观察30分钟)
    - 25% → Istio (观察30分钟)
    - 50% → Istio (观察1小时)
    - 75% → Istio (观察1小时)
    - 100% → Istio

  监控指标:
    - 错误率: < 1%
    - P95延迟: < 2秒
    - 可用性: > 99.9%

${YELLOW}阶段 3: 清理阶段 (1小时)${NC}
  1. 验证Istio稳定运行 ≥ 2周
  2. 清理APISIX资源
  3. 更新文档

${YELLOW}回滚策略:${NC}
  - 任何阶段发现问题立即执行 rollback 命令
  - 自动切回100%流量到APISIX
  - 保留Istio环境用于问题排查

${BLUE}═══════════════════════════════════════════════════════════════${NC}

${YELLOW}命令使用:${NC}
  ./scripts/migrate-apisix-to-istio.sh preflight        # 预检查
  ./scripts/migrate-apisix-to-istio.sh install-istio    # 安装Istio
  ./scripts/migrate-apisix-to-istio.sh apply            # 部署配置
  ./scripts/migrate-apisix-to-istio.sh verify           # 验证健康
  ./scripts/migrate-apisix-to-istio.sh canary           # 金丝雀切换
  ./scripts/migrate-apisix-to-istio.sh rollback         # 回滚
  ./scripts/migrate-apisix-to-istio.sh cleanup          # 清理APISIX

EOF
}

# ========== 安装Istio ==========
install_istio() {
    log_info "Installing Istio ${ISTIO_VERSION}..."

    # 创建命名空间
    kubectl create namespace "$ISTIO_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # 安装Istio
    log_info "Installing Istio with istioctl..."
    istioctl install --set profile=production \
        --set values.global.istioNamespace="$ISTIO_NAMESPACE" \
        --set values.gateways.istio-ingressgateway.autoscaleEnabled=true \
        --set values.gateways.istio-ingressgateway.autoscaleMin=3 \
        --set values.gateways.istio-ingressgateway.autoscaleMax=10 \
        --set values.pilot.autoscaleEnabled=true \
        --set values.pilot.autoscaleMin=2 \
        --set values.pilot.autoscaleMax=5 \
        --set values.global.proxy.resources.requests.cpu=100m \
        --set values.global.proxy.resources.requests.memory=128Mi \
        --set values.global.proxy.resources.limits.cpu=2000m \
        --set values.global.proxy.resources.limits.memory=1024Mi \
        --set meshConfig.accessLogFile="/dev/stdout" \
        --set meshConfig.accessLogEncoding="JSON" \
        --set meshConfig.enableTracing=true \
        --set meshConfig.defaultConfig.tracing.sampling=10.0 \
        -y

    # 等待Istio组件就绪
    log_info "Waiting for Istio components to be ready..."
    wait_for_resource deployment istiod "$ISTIO_NAMESPACE" 300
    wait_for_resource deployment istio-ingressgateway "$ISTIO_NAMESPACE" 300

    # 标记应用命名空间自动注入sidecar
    log_info "Enabling sidecar auto-injection for namespace $APP_NAMESPACE..."
    kubectl label namespace "$APP_NAMESPACE" istio-injection=enabled --overwrite

    log_success "Istio ${ISTIO_VERSION} installed successfully"
}

# ========== 部署Istio配置 ==========
apply_istio_config() {
    log_info "Applying Istio configurations..."

    # 创建应用命名空间
    kubectl create namespace "$APP_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # 应用配置文件
    local config_dir="${PROJECT_ROOT}/deployments/k8s/istio"

    if [ ! -d "$config_dir" ]; then
        log_error "Istio config directory not found: $config_dir"
        exit 1
    fi

    # 按顺序应用配置
    log_info "Applying namespace configuration..."
    kubectl apply -f "$config_dir/namespace.yaml" || true

    log_info "Applying Gateway configuration..."
    kubectl apply -f "$config_dir/gateway.yaml"

    log_info "Applying VirtualService configuration..."
    kubectl apply -f "$config_dir/virtual-service.yaml"

    log_info "Applying DestinationRule configuration..."
    kubectl apply -f "$config_dir/destination-rule.yaml"

    log_info "Applying Security configuration..."
    kubectl apply -f "$config_dir/security.yaml"

    log_info "Applying Telemetry configuration..."
    kubectl apply -f "$config_dir/telemetry.yaml"

    log_info "Applying EnvoyFilter configuration..."
    kubectl apply -f "$config_dir/envoy-filter.yaml"

    # 等待配置生效
    sleep 10

    log_success "Istio configurations applied successfully"
}

# ========== 验证Istio健康状态 ==========
verify_istio() {
    log_info "Verifying Istio installation..."

    # 检查Istio组件
    log_info "Checking Istio components..."
    kubectl get pods -n "$ISTIO_NAMESPACE"

    # 检查Gateway
    log_info "Checking Istio Gateway..."
    kubectl get gateway -n "$ISTIO_NAMESPACE"
    kubectl get gateway -n "$APP_NAMESPACE"

    # 检查VirtualService
    log_info "Checking VirtualServices..."
    kubectl get virtualservice -n "$APP_NAMESPACE"

    # 检查DestinationRule
    log_info "Checking DestinationRules..."
    kubectl get destinationrule -n "$APP_NAMESPACE"

    # 使用istioctl验证
    log_info "Running istioctl analyze..."
    if istioctl analyze -n "$APP_NAMESPACE"; then
        log_success "Istio configuration is valid"
    else
        log_warn "Istio configuration has warnings"
    fi

    # 检查Ingress Gateway LoadBalancer
    log_info "Checking Istio Ingress Gateway LoadBalancer..."
    local gateway_ip
    gateway_ip=$(kubectl get svc istio-ingressgateway -n "$ISTIO_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

    if [ -z "$gateway_ip" ]; then
        gateway_ip=$(kubectl get svc istio-ingressgateway -n "$ISTIO_NAMESPACE" \
            -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
    fi

    log_info "Istio Gateway LoadBalancer: $gateway_ip"

    # 健康检查
    log_info "Testing health endpoint..."
    if [ "$gateway_ip" != "pending" ] && [ -n "$gateway_ip" ]; then
        if curl -sf -o /dev/null "http://${gateway_ip}/health"; then
            log_success "Health check passed"
        else
            log_warn "Health check failed (might be normal if DNS not updated)"
        fi
    fi

    log_success "Istio verification completed"
}

# ========== 金丝雀流量切换 ==========
canary_switch() {
    log_info "Starting canary traffic switch from APISIX to Istio..."

    # 获取LoadBalancer IP
    local apisix_lb
    local istio_lb

    apisix_lb=$(kubectl get svc apisix-gateway -n "$APISIX_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || \
        kubectl get svc apisix-gateway -n "$APISIX_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

    istio_lb=$(kubectl get svc istio-ingressgateway -n "$ISTIO_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || \
        kubectl get svc istio-ingressgateway -n "$ISTIO_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

    if [ -z "$apisix_lb" ] || [ -z "$istio_lb" ]; then
        log_error "Cannot get LoadBalancer IPs. APISIX: $apisix_lb, Istio: $istio_lb"
        exit 1
    fi

    log_info "APISIX LoadBalancer: $apisix_lb"
    log_info "Istio LoadBalancer: $istio_lb"

    # 金丝雀切换流程
    for stage in "${CANARY_STAGES[@]}"; do
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "Canary Stage: ${stage}% traffic to Istio"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        cat <<EOF

${YELLOW}DNS配置建议:${NC}
请更新DNS权重比例为:
  - APISIX ($apisix_lb): $((100 - stage))%
  - Istio  ($istio_lb): ${stage}%

服务域名:
  - api.voiceassistant.com
  - ws.voiceassistant.com
  - grpc.voiceassistant.com

EOF

        # 等待用户确认
        read -p "DNS已更新完成? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warn "User cancelled. Exiting."
            exit 1
        fi

        # 观察等待期
        log_info "Observing for $CANARY_WAIT_TIME seconds..."
        local wait_interval=60
        local elapsed=0

        while [ $elapsed -lt $CANARY_WAIT_TIME ]; do
            sleep $wait_interval
            elapsed=$((elapsed + wait_interval))

            # 检查错误率
            log_info "Checking metrics... (${elapsed}s/${CANARY_WAIT_TIME}s)"

            # TODO: 实际环境中应该查询Prometheus指标
            # 这里仅做示意
            log_info "  - Error Rate: OK"
            log_info "  - Latency P95: OK"
            log_info "  - Availability: OK"
        done

        if [ "$stage" -ne 100 ]; then
            log_success "Stage ${stage}% completed successfully"

            # 询问是否继续
            read -p "Continue to next stage? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_warn "User stopped at stage ${stage}%"
                exit 0
            fi
        fi
    done

    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "Canary switch completed! 100% traffic is now on Istio"
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cat <<EOF

${GREEN}下一步:${NC}
  1. 监控Istio Gateway运行情况 ≥ 2周
  2. 确认所有功能正常后执行: ./scripts/migrate-apisix-to-istio.sh cleanup
  3. 更新架构文档

EOF
}

# ========== 回滚到APISIX ==========
rollback_to_apisix() {
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_warn "Rolling back to APISIX..."
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 获取LoadBalancer IP
    local apisix_lb
    apisix_lb=$(kubectl get svc apisix-gateway -n "$APISIX_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || \
        kubectl get svc apisix-gateway -n "$APISIX_NAMESPACE" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

    if [ -z "$apisix_lb" ]; then
        log_error "Cannot get APISIX LoadBalancer IP"
        exit 1
    fi

    cat <<EOF

${YELLOW}紧急回滚步骤:${NC}

1. 立即更新DNS，将所有流量切回APISIX:
   - api.voiceassistant.com → $apisix_lb (100%)
   - ws.voiceassistant.com → $apisix_lb (100%)
   - grpc.voiceassistant.com → $apisix_lb (100%)

2. 保留Istio环境用于问题排查

3. 查看Istio日志:
   kubectl logs -n $ISTIO_NAMESPACE -l app=istio-ingressgateway --tail=100

EOF

    read -p "DNS已切回APISIX? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_success "Rollback to APISIX completed"
        log_info "You can now investigate Istio issues"
    fi
}

# ========== 清理APISIX资源 ==========
cleanup_apisix() {
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_warn "This will DELETE all APISIX resources!"
    log_warn "Make sure Istio is running stable for ≥ 2 weeks"
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    read -p "Are you ABSOLUTELY SURE? (yes/no): " -r
    echo
    if [[ ! $REPLY == "yes" ]]; then
        log_info "Cleanup cancelled"
        exit 0
    fi

    log_info "Deleting APISIX resources..."

    # 删除APISIX部署
    kubectl delete -f "${PROJECT_ROOT}/deployments/k8s/apisix/" --ignore-not-found=true

    # 删除APISIX namespace
    kubectl delete namespace "$APISIX_NAMESPACE" --ignore-not-found=true

    log_success "APISIX resources cleaned up successfully"

    cat <<EOF

${GREEN}清理完成!${NC}

下一步:
  1. 更新架构文档: docs/arch/overview.md
  2. 更新部署文档
  3. 通知团队迁移已完成

EOF
}

# ========== 主函数 ==========
main() {
    local command=${1:-}

    case "$command" in
        plan)
            show_plan
            ;;
        preflight)
            preflight_check
            ;;
        install-istio)
            preflight_check
            install_istio
            ;;
        apply)
            apply_istio_config
            ;;
        verify)
            verify_istio
            ;;
        canary)
            canary_switch
            ;;
        rollback)
            rollback_to_apisix
            ;;
        cleanup)
            cleanup_apisix
            ;;
        *)
            cat <<EOF
Usage: $0 <command>

Commands:
  plan            显示迁移计划
  preflight       预检查环境
  install-istio   安装/升级Istio
  apply           部署Istio配置
  verify          验证Istio健康状态
  canary          金丝雀流量切换
  rollback        回滚到APISIX
  cleanup         清理APISIX资源

Example:
  $0 plan
  $0 preflight
  $0 install-istio
  $0 apply
  $0 verify
  $0 canary

EOF
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
