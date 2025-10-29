#!/bin/bash
# Proto代码生成脚本
# 用途：为新增的proto文件生成Go/Python代码

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Proto代码生成脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查protoc是否安装
if ! command -v protoc &> /dev/null; then
    echo -e "${RED}错误: protoc未安装${NC}"
    echo "请先安装protoc: https://grpc.io/docs/protoc-installation/"
    exit 1
fi

# 检查protoc-gen-go是否安装
if ! command -v protoc-gen-go &> /dev/null; then
    echo -e "${YELLOW}警告: protoc-gen-go未安装，正在安装...${NC}"
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
fi

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

echo -e "${GREEN}项目根目录: $PROJECT_ROOT${NC}"

# 创建输出目录
mkdir -p api/gen/go
mkdir -p api/gen/python

# 新增的proto文件列表
NEW_PROTOS=(
    "api/proto/rag/v1/rag.proto"
    "api/proto/retrieval/v1/retrieval.proto"
    "api/proto/agent/v1/agent.proto"
    "api/proto/voice/v1/voice.proto"
    "api/proto/multimodal/v1/multimodal.proto"
    "api/proto/indexing/v1/indexing.proto"
    "api/proto/vector-store/v1/vector_store.proto"
)

# 更新的proto文件
UPDATED_PROTOS=(
    "api/proto/knowledge/v1/knowledge.proto"
)

# 生成Go代码
echo -e "\n${GREEN}生成Go代码...${NC}"
for proto in "${NEW_PROTOS[@]}" "${UPDATED_PROTOS[@]}"; do
    if [ -f "$proto" ]; then
        echo -e "  处理: ${YELLOW}$proto${NC}"
        protoc \
            --proto_path=api/proto \
            --go_out=api/gen/go \
            --go_opt=paths=source_relative \
            --go-grpc_out=api/gen/go \
            --go-grpc_opt=paths=source_relative \
            "$proto"
        echo -e "  ${GREEN}✓${NC} 完成"
    else
        echo -e "  ${RED}✗${NC} 文件不存在: $proto"
    fi
done

# 生成Python代码
echo -e "\n${GREEN}生成Python代码...${NC}"
for proto in "${NEW_PROTOS[@]}" "${UPDATED_PROTOS[@]}"; do
    if [ -f "$proto" ]; then
        echo -e "  处理: ${YELLOW}$proto${NC}"
        python -m grpc_tools.protoc \
            --proto_path=api/proto \
            --python_out=api/gen/python \
            --grpc_python_out=api/gen/python \
            "$proto" || {
            echo -e "  ${YELLOW}警告: Python代码生成失败，可能需要安装grpcio-tools${NC}"
            echo "  运行: pip install grpcio-tools"
        }
        echo -e "  ${GREEN}✓${NC} 完成"
    fi
done

# 复制生成的Go代码到各服务
echo -e "\n${GREEN}复制Go代码到服务...${NC}"

# Knowledge Service
if [ -d "api/gen/go/knowledge/v1" ]; then
    mkdir -p cmd/knowledge-service/api/proto/knowledge/v1
    cp -r api/gen/go/knowledge/v1/* cmd/knowledge-service/api/proto/knowledge/v1/
    echo -e "  ${GREEN}✓${NC} knowledge-service"
fi

# 显示生成结果
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}代码生成完成！${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${YELLOW}生成的文件位置:${NC}"
echo "  - Go代码: api/gen/go/"
echo "  - Python代码: api/gen/python/"

echo -e "\n${YELLOW}下一步操作:${NC}"
echo "  1. 检查生成的代码是否正确"
echo "  2. 更新Go服务代码，移除临时类型定义"
echo "  3. 为Python服务添加gRPC服务器实现"
echo "  4. 运行测试确保兼容性"
echo "  5. 提交代码到版本控制"

echo -e "\n${YELLOW}Python服务gRPC支持:${NC}"
echo "  可选：为Python服务添加gRPC支持，参考文档："
echo "  docs/grpc-python-integration.md"

echo -e "\n${GREEN}完成！${NC}"
