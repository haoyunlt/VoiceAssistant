#!/bin/bash

# PostHog Kubernetes 快速部署脚本
# 用法: ./deploy-posthog.sh [self-hosted|cloud]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
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
        log_error "kubectl未安装，请先安装kubectl"
        exit 1
    fi
    
    # 检查集群连接
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到Kubernetes集群"
        exit 1
    fi
    
    log_info "前置条件检查通过"
}

# 部署自托管PostHog
deploy_self_hosted() {
    log_info "开始部署自托管PostHog..."
    
    # 创建命名空间
    log_info "创建PostHog命名空间..."
    kubectl create namespace posthog --dry-run=client -o yaml | kubectl apply -f -
    
    # 检查配置
    log_warn "请确保已经更新 posthog-deployment.yaml 中的以下配置:"
    log_warn "  1. Secret密码 (POSTHOG_DB_PASSWORD, CLICKHOUSE_PASSWORD, SECRET_KEY)"
    log_warn "  2. 域名配置 (SITE_URL, Ingress host)"
    read -p "是否已经更新配置? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "请先更新配置后再运行脚本"
        exit 1
    fi
    
    # 应用部署
    log_info "应用PostHog部署清单..."
    kubectl apply -f posthog-deployment.yaml
    
    # 等待Pod就绪
    log_info "等待PostHog Pod就绪 (这可能需要几分钟)..."
    kubectl wait --for=condition=ready pod -l app=posthog-postgres -n posthog --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=posthog-redis -n posthog --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=posthog-clickhouse -n posthog --timeout=300s || true
    kubectl wait --for=condition=ready pod -l app=posthog-web -n posthog --timeout=600s || true
    
    # 检查状态
    log_info "PostHog部署状态:"
    kubectl get pods -n posthog
    
    # 获取Ingress地址
    log_info "PostHog Ingress信息:"
    kubectl get ingress -n posthog
    
    log_info "✅ PostHog自托管部署完成!"
    log_info "请访问PostHog控制台创建项目并获取API Key"
}

# 配置云服务
deploy_cloud() {
    log_info "配置PostHog云服务..."
    
    # 提示用户获取API Key
    log_warn "请先完成以下步骤:"
    log_warn "  1. 访问 https://app.posthog.com (或 https://eu.posthog.com)"
    log_warn "  2. 注册并创建项目"
    log_warn "  3. 在 Project Settings 中获取 Project API Key"
    echo
    
    read -p "请输入PostHog API Key (格式: phc_xxxx): " POSTHOG_API_KEY
    
    if [[ ! $POSTHOG_API_KEY =~ ^phc_ ]]; then
        log_error "API Key格式不正确，应该以 phc_ 开头"
        exit 1
    fi
    
    # 选择区域
    echo "选择PostHog区域:"
    echo "  1. US (https://app.posthog.com)"
    echo "  2. EU (https://eu.posthog.com)"
    read -p "请选择 (1/2): " REGION
    
    if [[ $REGION == "2" ]]; then
        POSTHOG_HOST="https://eu.posthog.com"
    else
        POSTHOG_HOST="https://app.posthog.com"
    fi
    
    # 创建ConfigMap和Secret
    log_info "创建PostHog配置..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: model-router-posthog-config
  namespace: voiceassistant-prod
data:
  POSTHOG_ENABLED: "true"
  POSTHOG_HOST: "$POSTHOG_HOST"
---
apiVersion: v1
kind: Secret
metadata:
  name: model-router-posthog-secret
  namespace: voiceassistant-prod
type: Opaque
stringData:
  POSTHOG_API_KEY: "$POSTHOG_API_KEY"
EOF
    
    log_info "✅ PostHog云服务配置完成!"
}

# 部署Model Router
deploy_model_router() {
    log_info "部署Model Router..."
    
    # 创建命名空间
    kubectl create namespace voiceassistant-prod --dry-run=client -o yaml | kubectl apply -f -
    
    # 检查镜像配置
    log_warn "请确保已经更新 model-router-deployment.yaml 中的以下配置:"
    log_warn "  1. 镜像地址"
    log_warn "  2. PostHog API Key (Secret)"
    log_warn "  3. 数据库配置"
    log_warn "  4. LLM API Keys"
    read -p "是否已经更新配置? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "跳过Model Router部署，请手动部署"
        return
    fi
    
    # 应用部署
    log_info "应用Model Router部署清单..."
    kubectl apply -f model-router-deployment.yaml
    
    # 等待Pod就绪
    log_info "等待Model Router Pod就绪..."
    kubectl wait --for=condition=ready pod -l app=model-router -n voiceassistant-prod --timeout=300s || true
    
    # 检查状态
    log_info "Model Router部署状态:"
    kubectl get pods -n voiceassistant-prod -l app=model-router
    
    log_info "✅ Model Router部署完成!"
}

# 验证部署
verify_deployment() {
    log_info "验证部署..."
    
    # 检查PostHog (如果是自托管)
    if kubectl get namespace posthog &> /dev/null; then
        log_info "PostHog Pod状态:"
        kubectl get pods -n posthog
        
        log_info "PostHog Service状态:"
        kubectl get svc -n posthog
    fi
    
    # 检查Model Router
    if kubectl get namespace voiceassistant-prod &> /dev/null; then
        log_info "Model Router Pod状态:"
        kubectl get pods -n voiceassistant-prod -l app=model-router
        
        log_info "Model Router Service状态:"
        kubectl get svc -n voiceassistant-prod -l app=model-router
        
        # 测试连接
        POD_NAME=$(kubectl get pod -n voiceassistant-prod -l app=model-router -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        
        if [[ -n "$POD_NAME" ]]; then
            log_info "测试PostHog连接..."
            kubectl exec -n voiceassistant-prod $POD_NAME -- env | grep POSTHOG || true
        fi
    fi
    
    log_info "✅ 验证完成!"
}

# 显示使用说明
show_usage() {
    cat <<EOF
PostHog Kubernetes 部署脚本

用法:
  $0 [选项]

选项:
  self-hosted    部署自托管PostHog
  cloud          配置PostHog云服务
  model-router   部署Model Router
  verify         验证部署
  help           显示帮助信息

示例:
  # 部署自托管PostHog
  $0 self-hosted

  # 配置云服务
  $0 cloud

  # 部署Model Router
  $0 model-router

  # 完整部署 (自托管 + Model Router)
  $0 self-hosted && $0 model-router

  # 验证部署
  $0 verify

EOF
}

# 主函数
main() {
    case "${1:-help}" in
        self-hosted)
            check_prerequisites
            deploy_self_hosted
            ;;
        cloud)
            check_prerequisites
            deploy_cloud
            ;;
        model-router)
            check_prerequisites
            deploy_model_router
            ;;
        verify)
            verify_deployment
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "未知选项: $1"
            show_usage
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
