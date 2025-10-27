#!/bin/bash
# TODO扫描工具
# 用法: ./scripts/todo-scan.sh [options]

set -e

# 颜色定义
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助
show_help() {
    cat << EOF
TODO扫描工具 - VoiceAssistant项目

用法: $0 [选项]

选项:
    -h, --help          显示帮助信息
    -a, --all           显示所有TODO（默认）
    -p, --priority      按优先级过滤 (p0, p1, p2)
    -m, --module        按模块过滤 (voice, agent, retrieval, etc.)
    -f, --file FILE     扫描指定文件
    -c, --count         仅显示统计数
    -s, --summary       显示摘要
    --go                仅扫描Go文件
    --py                仅扫描Python文件

示例:
    $0 --all                        # 显示所有TODO
    $0 -p p0                        # 显示P0优先级TODO
    $0 -m voice                     # 显示语音引擎模块TODO
    $0 -f algo/voice-engine/*.py    # 扫描指定文件
    $0 -c                           # 显示统计数
    $0 -s                           # 显示摘要

EOF
}

# 统计TODO
count_todos() {
    local pattern="TODO|FIXME|XXX|HACK|待完善|待实现|未完成|WIP"
    local total=$(grep -ri "$pattern" --include="*.go" --include="*.py" . 2>/dev/null | wc -l | tr -d ' ')
    local go_count=$(grep -ri "$pattern" --include="*.go" . 2>/dev/null | wc -l | tr -d ' ')
    local py_count=$(grep -ri "$pattern" --include="*.py" . 2>/dev/null | wc -l | tr -d ' ')

    echo -e "${BLUE}=== TODO统计 ===${NC}"
    echo -e "总数: ${YELLOW}$total${NC}"
    echo -e "Go服务: ${GREEN}$go_count${NC}"
    echo -e "Python服务: ${GREEN}$py_count${NC}"
}

# 显示摘要
show_summary() {
    echo -e "${BLUE}=== TODO审查摘要 ===${NC}\n"
    echo -e "📊 ${YELLOW}总TODO数${NC}: 133个"
    echo -e "🔴 ${RED}P0阻塞项${NC}: 31个 (必须2周内完成)"
    echo -e "🟡 ${YELLOW}P1重要项${NC}: 34个 (影响体验)"
    echo -e "🟢 ${GREEN}P2优化项${NC}: 10个 (可延后)\n"

    echo -e "${BLUE}最紧急的5件事 (本周):${NC}"
    echo -e "1. Token黑名单 + JWT验证 (2天) - 安全漏洞"
    echo -e "2. 流式ASR + 流式响应 (3天) - 用户体验"
    echo -e "3. Embedding服务调用 (1天) - 检索核心"
    echo -e "4. 健康检查完善 (0.5天) - K8s部署"
    echo -e "5. 模型路由基线 (1天) - 成本控制\n"

    echo -e "${BLUE}详细文档:${NC}"
    echo -e "  📄 完整报告: ${GREEN}TODO_AUDIT_REPORT.md${NC}"
    echo -e "  📋 功能清单: ${GREEN}docs/INCOMPLETE_FEATURES_CHECKLIST.md${NC}"
    echo -e "  📊 追踪看板: ${GREEN}docs/TODO_TRACKER.md${NC}"
    echo -e "  👔 执行摘要: ${GREEN}docs/EXECUTIVE_SUMMARY_TODO.md${NC}"
    echo -e "  💻 文件索引: ${GREEN}docs/TODO_BY_FILE.md${NC}"
}

# 按模块过滤
filter_by_module() {
    local module=$1
    local pattern="TODO|FIXME|XXX|HACK|待完善|待实现|未完成|WIP"

    case $module in
        voice)
            echo -e "${BLUE}=== 语音引擎 TODO ===${NC}"
            grep -rn "$pattern" algo/voice-engine/ --include="*.py" 2>/dev/null || echo "未找到"
            ;;
        agent)
            echo -e "${BLUE}=== Agent引擎 TODO ===${NC}"
            grep -rn "$pattern" algo/agent-engine/ --include="*.py" 2>/dev/null || echo "未找到"
            ;;
        retrieval)
            echo -e "${BLUE}=== 检索服务 TODO ===${NC}"
            grep -rn "$pattern" algo/retrieval-service/ --include="*.py" 2>/dev/null || echo "未找到"
            ;;
        identity)
            echo -e "${BLUE}=== 身份服务 TODO ===${NC}"
            grep -rn "$pattern" cmd/identity-service/ --include="*.go" 2>/dev/null || echo "未找到"
            ;;
        model-router)
            echo -e "${BLUE}=== 模型路由 TODO ===${NC}"
            grep -rn "$pattern" cmd/model-router/ --include="*.go" 2>/dev/null || echo "未找到"
            ;;
        *)
            echo -e "${RED}未知模块: $module${NC}"
            echo -e "可用模块: voice, agent, retrieval, identity, model-router"
            exit 1
            ;;
    esac
}

# 扫描所有TODO
scan_all() {
    local pattern="TODO|FIXME|XXX|HACK|待完善|待实现|未完成|WIP"
    local filetype=$1

    case $filetype in
        go)
            echo -e "${BLUE}=== 扫描Go文件 ===${NC}"
            grep -rn "$pattern" --include="*.go" . 2>/dev/null | head -50
            ;;
        py)
            echo -e "${BLUE}=== 扫描Python文件 ===${NC}"
            grep -rn "$pattern" --include="*.py" . 2>/dev/null | head -50
            ;;
        *)
            echo -e "${BLUE}=== 扫描所有文件 ===${NC}"
            grep -rn "$pattern" --include="*.go" --include="*.py" . 2>/dev/null | head -50
            echo -e "\n${YELLOW}(仅显示前50条，使用 -c 查看完整统计)${NC}"
            ;;
    esac
}

# 主逻辑
main() {
    if [ $# -eq 0 ]; then
        show_summary
        exit 0
    fi

    case $1 in
        -h|--help)
            show_help
            ;;
        -c|--count)
            count_todos
            ;;
        -s|--summary)
            show_summary
            ;;
        -a|--all)
            scan_all all
            ;;
        --go)
            scan_all go
            ;;
        --py)
            scan_all py
            ;;
        -m|--module)
            if [ -z "$2" ]; then
                echo -e "${RED}错误: 需要指定模块名${NC}"
                exit 1
            fi
            filter_by_module $2
            ;;
        -f|--file)
            if [ -z "$2" ]; then
                echo -e "${RED}错误: 需要指定文件${NC}"
                exit 1
            fi
            grep -n "TODO|FIXME|XXX|HACK|待完善|待实现|未完成|WIP" $2 2>/dev/null || echo "未找到TODO"
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            echo -e "使用 -h 查看帮助"
            exit 1
            ;;
    esac
}

main "$@"
