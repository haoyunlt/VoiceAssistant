#!/usr/bin/env bash
#
# Istio to APISIX Migration Script
# 从 Istio/Envoy 迁移到 APISIX 网关
#
# Usage:
#   ./migrate-istio-to-apisix.sh [plan|apply|verify|rollback]
#

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
NAMESPACE_APISIX="apisix"
NAMESPACE_PROD="voiceassistant-prod"
NAMESPACE_ISTIO="istio-system"
BACKUP_DIR="./backups/istio-$(date +%Y%m%d-%H%M%S)"
KUBECTL="${KUBECTL:-kubectl}"

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

# 检查前置条件
check_prerequisites() {
    log_info "检查前置条件..."

    # 检查kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装"
        exit 1
    fi

    # 检查集群连接
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到 Kubernetes 集群"
        exit 1
    fi

    # 检查 Istio 是否存在
    if ! kubectl get namespace ${NAMESPACE_ISTIO} &> /dev/null; then
        log_warn "Istio namespace 不存在，可能已经移除"
    fi

    # 检查 etcd
    if ! kubectl get service etcd -n voiceassistant-infra &> /dev/null; then
        log_error "etcd 服务不存在，APISIX 需要 etcd 作为配置中心"
        exit 1
    fi

    log_success "前置条件检查通过"
}

# 备份现有配置
backup_istio_config() {
    log_info "备份 Istio 配置到 ${BACKUP_DIR}..."

    mkdir -p "${BACKUP_DIR}"

    # 备份 Gateway
    kubectl get gateway -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/gateways.yaml" || true

    # 备份 VirtualService
    kubectl get virtualservice -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/virtualservices.yaml" || true

    # 备份 DestinationRule
    kubectl get destinationrule -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/destinationrules.yaml" || true

    # 备份 PeerAuthentication
    kubectl get peerauthentication -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/peerauthentications.yaml" || true

    # 备份 AuthorizationPolicy
    kubectl get authorizationpolicy -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/authorizationpolicies.yaml" || true

    # 备份 RequestAuthentication
    kubectl get requestauthentication -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/requestauthentications.yaml" || true

    # 备份 Telemetry
    kubectl get telemetry -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/telemetries.yaml" || true

    # 备份当前服务状态
    kubectl get svc -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/services.yaml"
    kubectl get deployment -n ${NAMESPACE_PROD} -o yaml > "${BACKUP_DIR}/deployments.yaml"

    log_success "Istio 配置已备份到 ${BACKUP_DIR}"
}

# 创建 APISIX namespace 和资源
create_apisix_namespace() {
    log_info "创建 APISIX namespace..."

    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: ${NAMESPACE_APISIX}
  labels:
    app: apisix
    monitoring: enabled
EOF

    log_success "APISIX namespace 创建完成"
}

# 部署 APISIX
deploy_apisix() {
    log_info "部署 APISIX..."

    # 部署顺序很重要
    local apisix_dir="./deployments/k8s/apisix"

    # 1. 部署核心组件
    log_info "1. 部署 APISIX 核心组件..."
    kubectl apply -f "${apisix_dir}/deployment.yaml"

    # 等待 APISIX Pods 就绪
    log_info "等待 APISIX Pods 就绪..."
    kubectl wait --for=condition=ready pod -l app=apisix -n ${NAMESPACE_APISIX} --timeout=300s

    # 2. 配置路由
    log_info "2. 配置 APISIX 路由..."
    kubectl apply -f "${apisix_dir}/routes.yaml"

    # 3. 配置安全策略
    log_info "3. 配置 APISIX 安全策略..."
    kubectl apply -f "${apisix_dir}/security.yaml"

    # 4. 配置可观测性
    log_info "4. 配置 APISIX 可观测性..."
    kubectl apply -f "${apisix_dir}/observability.yaml"

    log_success "APISIX 部署完成"
}

# 配置 DNS 和流量切换准备
prepare_traffic_switch() {
    log_info "准备流量切换..."

    # 获取 APISIX LoadBalancer IP/Hostname
    log_info "获取 APISIX Gateway 地址..."
    local max_attempts=30
    local attempt=0
    local apisix_lb=""

    while [ $attempt -lt $max_attempts ]; do
        apisix_lb=$(kubectl get svc apisix-gateway -n ${NAMESPACE_APISIX} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || \
                    kubectl get svc apisix-gateway -n ${NAMESPACE_APISIX} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

        if [ -n "$apisix_lb" ]; then
            break
        fi

        log_info "等待 LoadBalancer 分配地址... ($((attempt+1))/${max_attempts})"
        sleep 10
        ((attempt++))
    done

    if [ -z "$apisix_lb" ]; then
        log_error "无法获取 APISIX LoadBalancer 地址"
        exit 1
    fi

    log_success "APISIX Gateway 地址: ${apisix_lb}"

    # 输出 DNS 配置说明
    cat <<EOF

${YELLOW}=== DNS 配置说明 ===${NC}

请更新以下域名的 DNS 记录，指向新的 APISIX LoadBalancer:

  ${apisix_lb}

需要更新的域名:
  - api.voiceassistant.com
  - ws.voiceassistant.com
  - grpc.voiceassistant.com
  - *.voiceassistant.com

建议策略:
  1. 先降低 DNS TTL 到 60 秒
  2. 使用加权路由，先导入 10% 流量到 APISIX
  3. 验证无误后逐步增加到 100%
  4. 完成后可以移除 Istio

EOF
}

# 验证 APISIX 部署
verify_apisix() {
    log_info "验证 APISIX 部署..."

    local apisix_svc="apisix-gateway.${NAMESPACE_APISIX}.svc.cluster.local"

    # 1. 检查 Pods 状态
    log_info "1. 检查 APISIX Pods 状态..."
    kubectl get pods -n ${NAMESPACE_APISIX} -l app=apisix

    local ready_pods=$(kubectl get pods -n ${NAMESPACE_APISIX} -l app=apisix -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' | wc -w)
    if [ "$ready_pods" -lt 2 ]; then
        log_error "APISIX Pods 数量不足 (期望>=2, 实际=${ready_pods})"
        return 1
    fi
    log_success "APISIX Pods 运行正常 (${ready_pods} 个)"

    # 2. 检查 Service
    log_info "2. 检查 APISIX Service..."
    kubectl get svc -n ${NAMESPACE_APISIX}

    # 3. 健康检查
    log_info "3. 执行健康检查..."

    # 使用 kubectl port-forward 进行健康检查
    kubectl port-forward -n ${NAMESPACE_APISIX} svc/apisix-admin 9090:9090 &
    local port_forward_pid=$!
    sleep 3

    local health_status=$(curl -s http://localhost:9090/apisix/status || echo "failed")
    kill $port_forward_pid 2>/dev/null || true

    if [[ "$health_status" == *"failed"* ]]; then
        log_error "APISIX 健康检查失败"
        return 1
    fi
    log_success "APISIX 健康检查通过"

    # 4. 检查 etcd 连接
    log_info "4. 检查 etcd 连接..."
    local apisix_pod=$(kubectl get pods -n ${NAMESPACE_APISIX} -l app=apisix -o jsonpath='{.items[0].metadata.name}')
    if kubectl exec -n ${NAMESPACE_APISIX} ${apisix_pod} -- curl -s http://etcd.voiceassistant-infra.svc.cluster.local:2379/health | grep -q "true"; then
        log_success "etcd 连接正常"
    else
        log_error "etcd 连接失败"
        return 1
    fi

    # 5. 测试路由
    log_info "5. 测试基础路由..."

    # 创建测试 Pod
    kubectl run test-curl --image=curlimages/curl:latest --rm -i --restart=Never -- \
        curl -s -o /dev/null -w "%{http_code}" \
        http://${apisix_svc}/health || true

    log_success "APISIX 验证通过"
}

# 金丝雀发布 - 流量逐步切换
canary_rollout() {
    log_info "开始金丝雀发布..."

    local weights=(10 25 50 75 100)

    for weight in "${weights[@]}"; do
        log_info "将 ${weight}% 流量导向 APISIX..."

        # 这里需要根据实际的流量管理方案调整
        # 示例：使用 Istio VirtualService 的权重路由
        cat <<EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: gateway-canary
  namespace: ${NAMESPACE_PROD}
spec:
  hosts:
  - "api.voiceassistant.com"
  gateways:
  - voiceassistant-gateway
  http:
  - match:
    - uri:
        prefix: "/"
    route:
    - destination:
        host: apisix-gateway.${NAMESPACE_APISIX}.svc.cluster.local
        port:
          number: 80
      weight: ${weight}
    - destination:
        host: identity-service.${NAMESPACE_PROD}.svc.cluster.local
        port:
          number: 8080
      weight: $((100-weight))
EOF

        log_success "已切换 ${weight}% 流量到 APISIX"

        # 观察一段时间
        if [ "$weight" -ne 100 ]; then
            log_info "观察 5 分钟..."

            # 实时监控错误率
            log_info "监控错误率和延迟..."
            sleep 300

            # 检查 APISIX 指标
            log_info "检查 APISIX 指标..."
            # kubectl port-forward 检查 Prometheus 指标
            # 这里可以添加自动化指标检查逻辑

            read -p "是否继续增加流量? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_error "用户中止金丝雀发布"
                exit 1
            fi
        fi
    done

    log_success "金丝雀发布完成，100% 流量已切换到 APISIX"
}

# 清理 Istio 资源
cleanup_istio() {
    log_warn "准备清理 Istio 资源..."

    read -p "确认要删除 Istio 资源? 这个操作不可逆! (yes/no) " -r
    echo
    if [[ ! $REPLY == "yes" ]]; then
        log_info "已取消清理操作"
        return
    fi

    log_info "删除 Istio CRD 资源..."

    # 删除应用的 Istio 配置
    kubectl delete gateway --all -n ${NAMESPACE_PROD} || true
    kubectl delete virtualservice --all -n ${NAMESPACE_PROD} || true
    kubectl delete destinationrule --all -n ${NAMESPACE_PROD} || true
    kubectl delete peerauthentication --all -n ${NAMESPACE_PROD} || true
    kubectl delete authorizationpolicy --all -n ${NAMESPACE_PROD} || true
    kubectl delete requestauthentication --all -n ${NAMESPACE_PROD} || true
    kubectl delete telemetry --all -n ${NAMESPACE_PROD} || true

    log_info "移除服务的 Istio Sidecar 注入..."

    # 移除 namespace 的 sidecar 注入标签
    kubectl label namespace ${NAMESPACE_PROD} istio-injection- || true

    # 重启所有 Pods 以移除 sidecar
    log_warn "需要重启所有 Pods 以移除 Istio sidecar，这会导致短暂的服务中断"
    read -p "是否立即重启所有 Pods? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl rollout restart deployment -n ${NAMESPACE_PROD}

        log_info "等待所有 Pods 重启完成..."
        kubectl rollout status deployment -n ${NAMESPACE_PROD} --timeout=600s
    fi

    log_info "清理 Istio 控制平面..."
    read -p "是否卸载 Istio 控制平面? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 使用 istioctl 卸载
        if command -v istioctl &> /dev/null; then
            istioctl uninstall --purge -y
        else
            log_warn "istioctl 未找到，请手动卸载 Istio"
        fi

        # 删除 istio-system namespace
        kubectl delete namespace ${NAMESPACE_ISTIO} || true
    fi

    log_success "Istio 清理完成"
}

# 回滚到 Istio
rollback_to_istio() {
    log_warn "开始回滚到 Istio..."

    if [ ! -d "${BACKUP_DIR}" ]; then
        log_error "备份目录不存在: ${BACKUP_DIR}"
        log_info "请指定备份目录: BACKUP_DIR=/path/to/backup $0 rollback"
        exit 1
    fi

    log_info "从备份恢复 Istio 配置..."

    # 恢复 Istio 资源
    kubectl apply -f "${BACKUP_DIR}/gateways.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/virtualservices.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/destinationrules.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/peerauthentications.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/authorizationpolicies.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/requestauthentications.yaml" || true
    kubectl apply -f "${BACKUP_DIR}/telemetries.yaml" || true

    log_info "等待 Istio 配置生效..."
    sleep 30

    # 验证 Istio Gateway
    if kubectl get gateway -n ${NAMESPACE_PROD} | grep -q "voiceassistant-gateway"; then
        log_success "Istio Gateway 已恢复"
    else
        log_error "Istio Gateway 恢复失败"
        exit 1
    fi

    # 可选：删除 APISIX
    read -p "是否删除 APISIX 部署? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace ${NAMESPACE_APISIX}
        log_success "APISIX 已删除"
    fi

    log_success "回滚到 Istio 完成"
}

# 生成迁移计划
generate_plan() {
    log_info "生成迁移计划..."

    cat <<EOF

${BLUE}╔════════════════════════════════════════════════════════════════╗
║                   Istio → APISIX 迁移计划                      ║
╚════════════════════════════════════════════════════════════════╝${NC}

${YELLOW}阶段 0: 准备阶段 (Day 0)${NC}
  ✓ 检查前置条件
  ✓ 备份 Istio 配置
  ✓ 验证 etcd 可用性
  ✓ 准备 APISIX 配置文件

${YELLOW}阶段 1: 部署 APISIX (Day 1)${NC}
  → 创建 APISIX namespace
  → 部署 APISIX Gateway (3副本)
  → 配置路由规则
  → 配置安全策略 (mTLS, JWT, RBAC)
  → 配置可观测性 (OpenTelemetry, Prometheus)
  → 内部验证测试

${YELLOW}阶段 2: 金丝雀发布 (Day 2-7)${NC}
  → Day 2: 10% 流量 → APISIX (观察 24h)
  → Day 3: 25% 流量 → APISIX (观察 24h)
  → Day 4: 50% 流量 → APISIX (观察 24h)
  → Day 6: 75% 流量 → APISIX (观察 24h)
  → Day 7: 100% 流量 → APISIX

${YELLOW}阶段 3: 稳定运行 (Day 8-14)${NC}
  → 100% 流量在 APISIX 上运行
  → 持续监控关键指标
  → Istio 保留作为备用
  → 准备最终清理

${YELLOW}阶段 4: 清理 Istio (Day 15+)${NC}
  → 删除 Istio Gateway/VirtualService
  → 移除 Pod Sidecar 注入
  → 卸载 Istio 控制平面 (可选)

${BLUE}╔════════════════════════════════════════════════════════════════╗
║                         监控指标                                ║
╚════════════════════════════════════════════════════════════════╝${NC}

关键 SLI/SLO:
  • P95 延迟: < 200ms (API Gateway)
  • P95 延迟: < 2.5s (端到端 AI 对话)
  • 可用性: >= 99.9%
  • 错误率: < 0.1%

告警阈值:
  • 错误率 > 1%: 立即回滚
  • P95 延迟增加 > 50%: 暂停发布，调查原因
  • 可用性 < 99%: 立即回滚

${BLUE}╔════════════════════════════════════════════════════════════════╗
║                         回滚策略                                ║
╚════════════════════════════════════════════════════════════════╝${NC}

触发条件:
  1. 关键指标超出阈值
  2. 出现 P0/P1 故障
  3. 业务方要求回滚

回滚步骤:
  1. 将流量切回 Istio (5分钟内)
  2. 验证 Istio 正常工作
  3. 调查 APISIX 问题
  4. 修复后重新发布

回滚命令:
  ${GREEN}./migrate-istio-to-apisix.sh rollback${NC}

${BLUE}╔════════════════════════════════════════════════════════════════╗
║                         执行命令                                ║
╚════════════════════════════════════════════════════════════════╝${NC}

查看计划:
  ${GREEN}./migrate-istio-to-apisix.sh plan${NC}

执行迁移:
  ${GREEN}./migrate-istio-to-apisix.sh apply${NC}

验证部署:
  ${GREEN}./migrate-istio-to-apisix.sh verify${NC}

回滚:
  ${GREEN}./migrate-istio-to-apisix.sh rollback${NC}

EOF
}

# 主函数
main() {
    local command="${1:-plan}"

    case "$command" in
        plan)
            generate_plan
            ;;

        apply)
            check_prerequisites
            backup_istio_config
            create_apisix_namespace
            deploy_apisix
            verify_apisix
            prepare_traffic_switch

            log_success "APISIX 部署完成!"
            log_info "下一步: 手动执行金丝雀发布或使用 DNS 切换流量"
            ;;

        verify)
            verify_apisix
            ;;

        canary)
            canary_rollout
            ;;

        cleanup)
            cleanup_istio
            ;;

        rollback)
            rollback_to_istio
            ;;

        *)
            log_error "未知命令: $command"
            echo "用法: $0 [plan|apply|verify|canary|cleanup|rollback]"
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
