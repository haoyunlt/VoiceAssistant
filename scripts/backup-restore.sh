#!/usr/bin/env bash
set -euo pipefail

# 备份和恢复脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

# 备份PostgreSQL
backup_postgres() {
    log_info "备份 PostgreSQL..."

    local backup_file="${BACKUP_DIR}/postgres_${TIMESTAMP}.sql"

    kubectl exec -n voiceassistant-infra postgres-0 -- \
        pg_dumpall -U postgres > "${backup_file}"

    gzip "${backup_file}"
    log_info "PostgreSQL备份完成: ${backup_file}.gz"
}

# 恢复PostgreSQL
restore_postgres() {
    local backup_file=$1

    if [ ! -f "${backup_file}" ]; then
        log_error "备份文件不存在: ${backup_file}"
        exit 1
    fi

    log_warn "即将恢复PostgreSQL，这将覆盖现有数据！"
    read -p "确认继续？(yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "取消恢复"
        exit 0
    fi

    log_info "恢复 PostgreSQL..."

    if [[ "${backup_file}" == *.gz ]]; then
        gunzip -c "${backup_file}" | kubectl exec -i -n voiceassistant-infra postgres-0 -- \
            psql -U postgres
    else
        kubectl exec -i -n voiceassistant-infra postgres-0 -- \
            psql -U postgres < "${backup_file}"
    fi

    log_info "PostgreSQL恢复完成"
}

# 备份Redis
backup_redis() {
    log_info "备份 Redis..."

    local backup_file="${BACKUP_DIR}/redis_${TIMESTAMP}.rdb"

    # 触发BGSAVE
    kubectl exec -n voiceassistant-infra redis-0 -- redis-cli BGSAVE

    # 等待BGSAVE完成
    while true; do
        status=$(kubectl exec -n voiceassistant-infra redis-0 -- redis-cli LASTSAVE)
        sleep 1
        new_status=$(kubectl exec -n voiceassistant-infra redis-0 -- redis-cli LASTSAVE)
        if [ "$status" != "$new_status" ]; then
            break
        fi
    done

    # 复制dump.rdb
    kubectl cp voiceassistant-infra/redis-0:/data/dump.rdb "${backup_file}"

    gzip "${backup_file}"
    log_info "Redis备份完成: ${backup_file}.gz"
}

# 备份Nacos配置
backup_nacos() {
    log_info "备份 Nacos 配置..."

    local backup_file="${BACKUP_DIR}/nacos_${TIMESTAMP}.json"

    # 通过Nacos API导出配置
    kubectl port-forward -n voiceassistant-infra svc/nacos 8848:8848 &
    local port_forward_pid=$!

    sleep 2

    curl -X GET "http://localhost:8848/nacos/v1/cs/configs?export=true&tenant=&group=" \
        -o "${backup_file}"

    kill $port_forward_pid || true

    gzip "${backup_file}"
    log_info "Nacos配置备份完成: ${backup_file}.gz"
}

# 备份Milvus
backup_milvus() {
    log_info "备份 Milvus..."

    log_warn "Milvus备份需要停机，请手动使用Milvus工具备份"
    log_info "参考: https://milvus.io/docs/backup.md"
}

# 备份Kubernetes配置
backup_k8s_configs() {
    log_info "备份 Kubernetes 配置..."

    local backup_dir="${BACKUP_DIR}/k8s_${TIMESTAMP}"
    mkdir -p "${backup_dir}"

    # 备份ConfigMaps
    kubectl get configmap -n voiceassistant-prod -o yaml > "${backup_dir}/configmaps.yaml"

    # 备份Secrets
    kubectl get secret -n voiceassistant-prod -o yaml > "${backup_dir}/secrets.yaml"

    # 备份Services
    kubectl get svc -n voiceassistant-prod -o yaml > "${backup_dir}/services.yaml"

    # 备份Deployments
    kubectl get deployment -n voiceassistant-prod -o yaml > "${backup_dir}/deployments.yaml"

    # 备份StatefulSets
    kubectl get statefulset -n voiceassistant-prod -o yaml > "${backup_dir}/statefulsets.yaml"

    # 备份Istio配置
    kubectl get gateway,virtualservice,destinationrule -n voiceassistant-prod -o yaml \
        > "${backup_dir}/istio.yaml"

    tar -czf "${backup_dir}.tar.gz" -C "${BACKUP_DIR}" "k8s_${TIMESTAMP}"
    rm -rf "${backup_dir}"

    log_info "Kubernetes配置备份完成: ${backup_dir}.tar.gz"
}

# 全量备份
backup_all() {
    log_info "开始全量备份..."

    backup_postgres
    backup_redis
    backup_nacos
    backup_k8s_configs

    log_info "全量备份完成，备份目录: ${BACKUP_DIR}"
    log_info "备份文件列表:"
    ls -lh "${BACKUP_DIR}" | grep "${TIMESTAMP}"
}

# 列出备份
list_backups() {
    log_info "可用备份列表:"
    ls -lh "${BACKUP_DIR}"
}

# 清理旧备份
cleanup_old_backups() {
    local keep_days=${1:-7}

    log_info "清理 ${keep_days} 天前的备份..."

    find "${BACKUP_DIR}" -type f -mtime +${keep_days} -delete

    log_info "清理完成"
}

# 显示帮助
show_help() {
    cat << EOF
备份和恢复脚本

用法: $0 <命令> [选项]

命令:
    backup-all              全量备份
    backup-postgres         备份PostgreSQL
    backup-redis            备份Redis
    backup-nacos            备份Nacos配置
    backup-k8s              备份Kubernetes配置
    restore-postgres <file> 恢复PostgreSQL
    list                    列出备份文件
    cleanup [days]          清理旧备份（默认7天）

示例:
    $0 backup-all                           # 全量备份
    $0 restore-postgres backups/postgres_*.sql.gz  # 恢复数据库
    $0 cleanup 30                           # 清理30天前的备份
EOF
}

# 主函数
main() {
    case "${1:-help}" in
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
            backup_k8s_configs
            ;;
        restore-postgres)
            restore_postgres "${2:-}"
            ;;
        list)
            list_backups
            ;;
        cleanup)
            cleanup_old_backups "${2:-7}"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
