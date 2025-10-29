#!/bin/bash
# Agent Engine Iteration 2 API 测试脚本
# 快速测试 Self-RAG、智能记忆和 Multi-Agent 协作功能

set -e

# 配置
BASE_URL="${BASE_URL:-http://localhost:8003}"
TOKEN="${TOKEN:-test_token_12345}"

echo "======================================"
echo "Agent Engine Iteration 2 API 测试"
echo "======================================"
echo "Base URL: $BASE_URL"
echo ""

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 测试函数
test_api() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4

    echo -e "${BLUE}测试: $name${NC}"
    echo "Endpoint: $method $endpoint"

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" \
            -X GET "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" \
            -X POST "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✓ 成功 (HTTP $http_code)${NC}"
        echo "Response:"
        echo "$body" | python -m json.tool 2>/dev/null || echo "$body"
    else
        echo -e "${RED}✗ 失败 (HTTP $http_code)${NC}"
        echo "Response:"
        echo "$body"
    fi
    echo ""
}

# ==================== Self-RAG 测试 ====================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}1. Self-RAG 功能测试${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 测试 Self-RAG 查询
test_api "Self-RAG 查询" "POST" "/self-rag/query" '{
  "query": "什么是RAG，它如何帮助LLM减少幻觉？",
  "mode": "adaptive",
  "enable_citations": true,
  "max_refinements": 2
}'

# 获取 Self-RAG 统计
test_api "Self-RAG 统计" "GET" "/self-rag/stats" ""

# ==================== 智能记忆测试 ====================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}2. 智能记忆管理功能测试${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 添加记忆
test_api "添加长期记忆" "POST" "/smart-memory/add" '{
  "content": "用户喜欢技术文档，关注AI和RAG技术",
  "tier": "long_term",
  "importance": 0.9,
  "metadata": {
    "category": "user_preference"
  }
}'

test_api "添加短期记忆" "POST" "/smart-memory/add" '{
  "content": "用户询问了关于 RAG 的问题",
  "tier": "short_term",
  "importance": 0.7
}'

test_api "添加工作记忆" "POST" "/smart-memory/add" '{
  "content": "当前任务是学习 Self-RAG 技术",
  "tier": "working",
  "importance": 0.8
}'

# 检索记忆
test_api "检索记忆" "POST" "/smart-memory/retrieve" '{
  "query": "用户对RAG技术感兴趣吗？",
  "top_k": 5,
  "min_importance": 0.5
}'

# 压缩记忆
test_api "压缩短期记忆" "POST" "/smart-memory/compress?tier=short_term" ""

# 维护记忆
test_api "执行记忆维护" "POST" "/smart-memory/maintain" ""

# 获取记忆统计
test_api "记忆统计" "GET" "/smart-memory/stats" ""

# ==================== Multi-Agent 测试 ====================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}3. Multi-Agent 协作功能测试${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 注册 Agents
test_api "注册 Researcher Agent" "POST" "/multi-agent/agents/register" '{
  "agent_id": "researcher_01",
  "role": "researcher",
  "tools": ["search_tool", "knowledge_tool"]
}'

test_api "注册 Planner Agent" "POST" "/multi-agent/agents/register" '{
  "agent_id": "planner_01",
  "role": "planner",
  "tools": ["planning_tool"]
}'

test_api "注册 Executor Agent" "POST" "/multi-agent/agents/register" '{
  "agent_id": "executor_01",
  "role": "executor",
  "tools": ["calculator_tool", "data_tool"]
}'

# 列出所有 Agents
test_api "列出所有 Agents" "GET" "/multi-agent/agents" ""

# 并行协作
test_api "并行协作任务" "POST" "/multi-agent/collaborate" '{
  "task": "分析人工智能在医疗领域的应用现状和未来趋势",
  "mode": "parallel",
  "agent_ids": ["researcher_01", "planner_01", "executor_01"],
  "priority": 8
}'

# 获取 Multi-Agent 统计
test_api "Multi-Agent 统计" "GET" "/multi-agent/stats" ""

# ==================== 健康检查 ====================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}4. 健康检查${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

test_api "健康检查" "GET" "/health" ""
test_api "就绪检查" "GET" "/ready" ""

# ==================== 总结 ====================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}测试完成！${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "提示："
echo "1. 查看完整 API 文档: $BASE_URL/docs"
echo "2. 查看 Prometheus 指标: $BASE_URL/metrics"
echo "3. 运行演示: python examples/iter2_integration_demo.py"
echo "4. 查看集成指南: docs/ITER2_INTEGRATION_GUIDE.md"
echo ""
