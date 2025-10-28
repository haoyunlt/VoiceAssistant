#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper 备份恢复脚本
# 用途: 备份和恢复 PostgreSQL/Redis/Nacos 配置/Milvus 数据

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
NAMESPACE_INFRA="voiceassistant-infra"
NAMESPACE_PROD="voiceassistant-prod"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# 检查依赖
check_dependencies() {
    if ! command -v kubectl &> /dev/null; then
        log_fail "kubectl 未安装"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_fail "无法连接到 Kubernetes 集群"
        exit 1
    fi

    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    log_success "备份目录: $BACKUP_DIR"
}

# 备份 PostgreSQL
backup_postgres() {
    log_info "备份 PostgreSQL..."

    local pg_pod=$(kubectl get pod -n "$NAMESPACE_INFRA" -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$pg_pod" ]; then
        log_fail "未找到 PostgreSQL Pod"
        return 1
    fi

    local backup_file="${BACKUP_DIR}/postgres_${TIMESTAMP}.sql"

    log_info "执行 pg_dump..."
    if kubectl exec -n "$NAMESPACE_INFRA" "$pg_pod" -- \
        pg_dumpall -U voiceassistant > "$backup_file"; then

        # 压缩备份
        gzip "$backup_file"
        backup_file="${backup_file}.gz"

        local size=$(du -h "$backup_file" | cut -f1)
        log_success "PostgreSQL 备份完成: $backup_file ($size)"
    else
        log_fail "PostgreSQL 备份失败"
        return 1
    fi
}

# 恢复 PostgreSQL
restore_postgres() {
    local backup_file=$1

    if [ ! -f "$backup_file" ]; then
        log_fail "备份文件不存在: $backup_file"
        return 1
    fi

    log_warn "恢复 PostgreSQL 将覆盖现有数据！"
    read -p "确认恢复？ (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "取消恢复"
        return 0
    fi

    local pg_pod=$(kubectl get pod -n "$NAMESPACE_INFRA" -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$pg_pod" ]; then
        log_fail "未找到 PostgreSQL Pod"
        return 1
    fi

    log_info "恢复 PostgreSQL..."

    # 解压（如果是压缩文件）
    local sql_file="$backup_file"
    if [[ "$backup_file" == *.gz ]]; then
        sql_file="${backup_file%.gz}"
        gunzip -c "$backup_file" > "$sql_file"
    fi

    # 恢复数据库
    if kubectl exec -i -n "$NAMESPACE_INFRA" "$pg_pod" -- \
        psql -U voiceassistant < "$sql_file"; then
        log_success "PostgreSQL 恢复完成"
    else
        log_fail "PostgreSQL 恢复失败"
        return 1
    fi

    # 清理临时文件
    if [[ "$backup_file" == *.gz ]]; then
        rm -f "$sql_file"
    fi
}

# 备份 Redis
backup_redis() {
    log_info "备份 Redis..."

    local redis_pod=$(kubectl get pod -n "$NAMESPACE_INFRA" -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$redis_pod" ]; then
        log_fail "未找到 Redis Pod"
        return 1
    fi

    local backup_file="${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

    # 触发 Redis 保存
    log_info "触发 Redis SAVE..."
    kubectl exec -n "$NAMESPACE_INFRA" "$redis_pod" -- redis-cli SAVE

    # 复制 RDB 文件
    log_info "复制 dump.rdb..."
    kubectl cp "$NAMESPACE_INFRA/$redis_pod:/data/dump.rdb" "$backup_file"

    # 压缩备份
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    local size=$(du -h "$backup_file" | cut -f1)
    log_success "Redis 备份完成: $backup_file ($size)"
}

# 恢复 Redis
restore_redis() {
    local backup_file=$1

    if [ ! -f "$backup_file" ]; then
        log_fail "备份文件不存在: $backup_file"
        return 1
    fi

    log_warn "恢复 Redis 将覆盖现有数据！"
    read -p "确认恢复？ (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "取消恢复"
        return 0
    fi

    local redis_pod=$(kubectl get pod -n "$NAMESPACE_INFRA" -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$redis_pod" ]; then
        log_fail "未找到 Redis Pod"
        return 1
    fi

    log_info "恢复 Redis..."

    # 解压
    local rdb_file="$backup_file"
    if [[ "$backup_file" == *.gz ]]; then
        rdb_file="${backup_file%.gz}"
        gunzip -c "$backup_file" > "$rdb_file"
    fi

    # 停止 Redis
    log_info "停止 Redis..."
    kubectl exec -n "$NAMESPACE_INFRA" "$redis_pod" -- redis-cli SHUTDOWN || true
    sleep 2

    # 复制 RDB 文件
    log_info "复制 RDB 文件..."
    kubectl cp "$rdb_file" "$NAMESPACE_INFRA/$redis_pod:/data/dump.rdb"

    # 重启 Pod
    log_info "重启 Redis Pod..."
    kubectl delete pod -n "$NAMESPACE_INFRA" "$redis_pod"

    # 等待 Pod 重启
    kubectl wait --for=condition=ready pod -l app=redis -n "$NAMESPACE_INFRA" --timeout=120s

    log_success "Redis 恢复完成"

    # 清理临时文件
    if [[ "$backup_file" == *.gz ]]; then
        rm -f "$rdb_file"
    fi
}

# 备份 Nacos 配置
backup_nacos() {
    log_info "备份 Nacos 配置..."

    local nacos_pod=$(kubectl get pod -n "$NAMESPACE_INFRA" -l app=nacos -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [ -z "$nacos_pod" ]; then
        log_fail "未找到 Nacos Pod"
        return 1
    fi

    local backup_file="${BACKUP_DIR}/nacos_config_${TIMESTAMP}.zip"

    # 使用 Nacos API 导出配置
    log_info "导出 Nacos 配置..."
    kubectl port-forward -n "$NAMESPACE_INFRA" "$nacos_pod" 18848:8848 &> /dev/null &
    local pf_pid=$!
    sleep 2

    # 获取所有配置
    if curl -s "http://localhost:18848/nacos/v1/cs/configs?dataId=&group=&tenant=&search=accurate" \
        -o "${backup_file%.zip}.json"; then

        # 压缩
        zip -j "$backup_file" "${backup_file%.zip}.json" &> /dev/null
        rm -f "${backup_file%.zip}.json"

        local size=$(du -h "$backup_file" | cut -f1)
        log_success "Nacos 配置备份完成: $backup_file ($size)"
    else
        log_fail "Nacos 配置备份失败"
    fi

    kill "$pf_pid" 2>/dev/null || true
}

# 备份 Kubernetes 资源
backup_k8s_resources() {
    log_info "备份 Kubernetes 资源定义..."

    local backup_file="${BACKUP_DIR}/k8s_resources_${TIMESTAMP}.tar.gz"
    local temp_dir="/tmp/voicehelper_k8s_backup_$$"

    mkdir -p "$temp_dir"

    # 备份应用 namespace 的资源
    kubectl get all,configmap,secret,pvc -n "$NAMESPACE_PROD" -o yaml > "$temp_dir/prod_resources.yaml"
    kubectl get all,configmap,secret,pvc -n "$NAMESPACE_INFRA" -o yaml > "$temp_dir/infra_resources.yaml"

    # 备份 Istio 配置
    if kubectl get namespace istio-system &> /dev/null; then
        kubectl get gateway,virtualservice,destinationrule,peerauthentication -n "$NAMESPACE_PROD" -o yaml > "$temp_dir/istio_config.yaml"
    fi

    # 打包
    tar -czf "$backup_file" -C "$temp_dir" .
    rm -rf "$temp_dir"

    local size=$(du -h "$backup_file" | cut -f1)
    log_success "K8s 资源备份完成: $backup_file ($size)"
}

# 备份所有
backup_all() {
    log_info "========================================"
    log_info "开始全量备份"
    log_info "========================================"
    echo ""

    backup_postgres || log_warn "PostgreSQL 备份失败，继续..."
    echo ""

    backup_redis || log_warn "Redis 备份失败，继续..."
    echo ""

    backup_nacos || log_warn "Nacos 备份失败，继续..."
    echo ""

    backup_k8s_resources || log_warn "K8s 资源备份失败，继续..."
    echo ""

    log_success "全量备份完成！"
    log_info "备份目录: $BACKUP_DIR"
    log_info "备份列表:"
    ls -lh "$BACKUP_DIR"/*_${TIMESTAMP}* 2>/dev/null || true
}

# 清理旧备份
cleanup_old_backups() {
    local keep_days=${1:-30}

    log_info "清理 ${keep_days} 天前的备份..."

    if [ ! -d "$BACKUP_DIR" ]; then
        log_warn "备份目录不存在"
        return 0
    fi

    local count=$(find "$BACKUP_DIR" -type f -mtime "+${keep_days}" | wc -l)

    if [ "$count" -eq 0 ]; then
        log_info "没有需要清理的旧备份"
        return 0
    fi

    log_info "找到 $count 个旧备份文件"

    find "$BACKUP_DIR" -type f -mtime "+${keep_days}" -delete

    log_success "旧备份清理完成"
}

# 列出备份
list_backups() {
    log_info "备份列表:"
    echo ""

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        log_warn "没有备份文件"
        return 0
    fi

    echo "PostgreSQL 备份:"
    ls -lh "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    echo ""

    echo "Redis 备份:"
    ls -lh "$BACKUP_DIR"/redis_*.rdb.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    echo ""

    echo "Nacos 备份:"
    ls -lh "$BACKUP_DIR"/nacos_config_*.zip 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    echo ""

    echo "K8s 资源备份:"
    ls -lh "$BACKUP_DIR"/k8s_resources_*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    echo ""
}

# 显示帮助
show_help() {
    cat << EOF
VoiceHelper 备份恢复脚本

用法: $0 <命令> [参数]

备份命令:
  backup-all            备份所有服务
  backup-postgres       备份 PostgreSQL
  backup-redis          备份 Redis
  backup-nacos          备份 Nacos 配置
  backup-k8s            备份 K8s 资源定义

恢复命令:
  restore-postgres <file>   恢复 PostgreSQL
  restore-redis <file>      恢复 Redis

管理命令:
  list                  列出所有备份
  cleanup [days]        清理旧备份（默认30天）
  -h, --help            显示帮助信息

示例:
  $0 backup-all                               # 备份所有
  $0 backup-postgres                          # 仅备份 PostgreSQL
  $0 restore-postgres backups/postgres_*.gz   # 恢复 PostgreSQL
  $0 cleanup 7                                # 清理7天前的备份
  $0 list                                     # 列出备份

备份目录: $BACKUP_DIR

EOF
}

# 主函数
main() {
    local command="${1:-}"

    if [ -z "$command" ]; then
        show_help
        exit 1
    fi

    check_dependencies
    echo ""

    case "$command" in
        backup-all)
            backup_all
            ;;
        backup-postgres)
            backup_postgres
            ;;
        backup-redis)
            backup_redis
            ;;
        backup-nacos)
            backup_nacos
            ;;
        backup-k8s)
            backup_k8s_resources
            ;;
        restore-postgres)
            if [ -z "${2:-}" ]; then
                log_fail "请指定备份文件"
                exit 1
            fi
            restore_postgres "$2"
            ;;
        restore-redis)
            if [ -z "${2:-}" ]; then
                log_fail "请指定备份文件"
                exit 1
            fi
            restore_redis "$2"
            ;;
        list)
            list_backups
            ;;
        cleanup)
            cleanup_old_backups "${2:-30}"
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_fail "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
