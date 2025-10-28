#!/usr/bin/env bash
set -euo pipefail

# VoiceHelper Protobuf 代码生成脚本
# 用途: 从 .proto 文件生成 Go 和 Python 代码

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROTO_DIR="${PROJECT_ROOT}/api/proto"

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
    log_info "检查 protobuf 工具链..."

    if ! command -v protoc &> /dev/null; then
        log_fail "protoc 未安装"
        log_info "安装方法:"
        log_info "  macOS: brew install protobuf"
        log_info "  Ubuntu: apt-get install protobuf-compiler"
        exit 1
    fi

    local protoc_version=$(protoc --version | awk '{print $2}')
    log_success "protoc 版本: $protoc_version"

    # 检查 Go 插件
    if ! command -v protoc-gen-go &> /dev/null; then
        log_warn "protoc-gen-go 未安装，尝试安装..."
        go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    fi

    if ! command -v protoc-gen-go-grpc &> /dev/null; then
        log_warn "protoc-gen-go-grpc 未安装，尝试安装..."
        go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
    fi

    # 检查 Python 插件
    if ! command -v python3 &> /dev/null; then
        log_fail "python3 未安装"
        exit 1
    fi

    if ! python3 -c "import grpc_tools" 2>/dev/null; then
        log_warn "grpcio-tools 未安装，尝试安装..."
        pip3 install grpcio-tools
    fi

    log_success "依赖检查完成"
}

# 生成 Go 代码
generate_go_code() {
    local proto_file=$1
    local module_name=$(basename $(dirname "$proto_file"))

    log_info "生成 Go 代码: $module_name"

    # 输出目录
    local go_out_dir="${PROJECT_ROOT}/api/gen/go/${module_name}"
    mkdir -p "$go_out_dir"

    # 生成代码
    if protoc \
        --proto_path="${PROTO_DIR}" \
        --go_out="$go_out_dir" \
        --go_opt=paths=source_relative \
        --go-grpc_out="$go_out_dir" \
        --go-grpc_opt=paths=source_relative \
        "$proto_file"; then
        log_success "Go 代码生成成功: $go_out_dir"
    else
        log_fail "Go 代码生成失败: $proto_file"
        return 1
    fi
}

# 生成 Python 代码
generate_python_code() {
    local proto_file=$1
    local module_name=$(basename $(dirname "$proto_file"))

    log_info "生成 Python 代码: $module_name"

    # 输出目录
    local py_out_dir="${PROJECT_ROOT}/api/gen/python/${module_name}"
    mkdir -p "$py_out_dir"

    # 生成代码
    if python3 -m grpc_tools.protoc \
        --proto_path="${PROTO_DIR}" \
        --python_out="$py_out_dir" \
        --grpc_python_out="$py_out_dir" \
        "$proto_file"; then

        # 创建 __init__.py
        touch "$py_out_dir/__init__.py"

        log_success "Python 代码生成成功: $py_out_dir"
    else
        log_fail "Python 代码生成失败: $proto_file"
        return 1
    fi
}

# 生成 OpenAPI 文档 (可选)
generate_openapi() {
    log_info "生成 OpenAPI 文档..."

    if ! command -v protoc-gen-openapiv2 &> /dev/null; then
        log_warn "protoc-gen-openapiv2 未安装，跳过 OpenAPI 生成"
        log_info "安装方法: go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-openapiv2@latest"
        return 0
    fi

    local openapi_out_dir="${PROJECT_ROOT}/api/gen/openapi"
    mkdir -p "$openapi_out_dir"

    # 生成所有服务的 OpenAPI 文档
    find "${PROTO_DIR}" -name "*.proto" | while read -r proto_file; do
        local module_name=$(basename $(dirname "$proto_file"))

        protoc \
            --proto_path="${PROTO_DIR}" \
            --openapiv2_out="$openapi_out_dir" \
            --openapiv2_opt=logtostderr=true \
            "$proto_file" 2>/dev/null || true
    done

    log_success "OpenAPI 文档生成完成: $openapi_out_dir"
}

# 处理所有 proto 文件
process_all_protos() {
    log_info "扫描 proto 文件..."

    if [ ! -d "$PROTO_DIR" ]; then
        log_fail "proto 目录不存在: $PROTO_DIR"
        exit 1
    fi

    local proto_count=0
    local success_count=0
    local fail_count=0

    # 查找所有 .proto 文件
    while IFS= read -r -d '' proto_file; do
        proto_count=$((proto_count + 1))

        echo ""
        log_info "处理: $proto_file"

        if generate_go_code "$proto_file" && generate_python_code "$proto_file"; then
            success_count=$((success_count + 1))
        else
            fail_count=$((fail_count + 1))
        fi
    done < <(find "${PROTO_DIR}" -name "*.proto" -print0)

    echo ""
    log_info "========================================"
    log_info "代码生成完成"
    log_info "========================================"
    echo "总文件数: $proto_count"
    echo -e "${GREEN}成功: $success_count${NC}"
    echo -e "${RED}失败: $fail_count${NC}"
    echo ""

    if [ "$fail_count" -eq 0 ]; then
        log_success "所有 proto 文件处理成功！"
        return 0
    else
        log_fail "部分 proto 文件处理失败"
        return 1
    fi
}

# 清理生成的代码
clean_generated() {
    log_info "清理已生成的代码..."

    local gen_dir="${PROJECT_ROOT}/api/gen"

    if [ -d "$gen_dir" ]; then
        rm -rf "$gen_dir"
        log_success "已清理: $gen_dir"
    else
        log_warn "生成目录不存在，无需清理"
    fi
}

# 生成特定模块
generate_module() {
    local module=$1

    log_info "生成模块: $module"

    local module_dir="${PROTO_DIR}/${module}"

    if [ ! -d "$module_dir" ]; then
        log_fail "模块目录不存在: $module_dir"
        exit 1
    fi

    find "$module_dir" -name "*.proto" | while read -r proto_file; do
        log_info "处理: $proto_file"
        generate_go_code "$proto_file"
        generate_python_code "$proto_file"
    done

    log_success "模块 $module 代码生成完成"
}

# 验证 proto 文件
validate_protos() {
    log_info "验证 proto 文件..."

    local error_count=0

    find "${PROTO_DIR}" -name "*.proto" | while read -r proto_file; do
        if ! protoc --proto_path="${PROTO_DIR}" --decode_raw < /dev/null "$proto_file" 2>/dev/null; then
            # 尝试编译验证
            if ! protoc --proto_path="${PROTO_DIR}" --descriptor_set_out=/dev/null "$proto_file" 2>&1 | grep -q "error"; then
                log_success "验证通过: $(basename $proto_file)"
            else
                log_fail "验证失败: $proto_file"
                error_count=$((error_count + 1))
            fi
        fi
    done

    if [ "$error_count" -eq 0 ]; then
        log_success "所有 proto 文件验证通过"
        return 0
    else
        log_fail "$error_count 个 proto 文件验证失败"
        return 1
    fi
}

# 显示帮助
show_help() {
    cat << EOF
VoiceHelper Protobuf 代码生成脚本

用法: $0 [命令] [选项]

命令:
  all              生成所有 proto 文件 (默认)
  module <name>    生成指定模块
  clean            清理已生成的代码
  validate         验证 proto 文件语法
  openapi          生成 OpenAPI 文档
  -h, --help       显示帮助信息

示例:
  $0                          # 生成所有代码
  $0 module identity          # 仅生成 identity 模块
  $0 clean                    # 清理生成的代码
  $0 validate                 # 验证 proto 文件

生成目录:
  Go:      api/gen/go/<module>/
  Python:  api/gen/python/<module>/
  OpenAPI: api/gen/openapi/

EOF
}

# 主函数
main() {
    local command="${1:-all}"

    case "$command" in
        all)
            log_info "========================================"
            log_info "Protobuf 代码生成"
            log_info "========================================"
            echo ""
            check_dependencies
            echo ""
            process_all_protos
            echo ""
            generate_openapi
            ;;
        module)
            if [ -z "${2:-}" ]; then
                log_fail "请指定模块名称"
                show_help
                exit 1
            fi
            check_dependencies
            generate_module "$2"
            ;;
        clean)
            clean_generated
            ;;
        validate)
            validate_protos
            ;;
        openapi)
            check_dependencies
            generate_openapi
            ;;
        -h|--help)
            show_help
            exit 0
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
