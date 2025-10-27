#!/bin/bash
# 测试服务集成

set -e

BASE_URL=${BASE_URL:-"http://localhost"}

echo "🧪 测试服务集成..."

# 测试Agent Engine - knowledge_base工具
echo -e "\n[1/5] 测试Agent Engine (knowledge_base工具)..."
curl -X POST "$BASE_URL:8003/api/v1/agent/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "查询关于RAG的信息",
    "tools": ["knowledge_base"],
    "max_iterations": 5
  }' \
  -w "\nStatus: %{http_code}\n" || echo "❌ Agent测试失败"

# 测试RAG Engine
echo -e "\n[2/5] 测试RAG Engine..."
curl -X POST "$BASE_URL:8006/api/v1/rag/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG？",
    "knowledge_base_id": "test_kb",
    "tenant_id": "test_tenant",
    "top_k": 5
  }' \
  -w "\nStatus: %{http_code}\n" || echo "❌ RAG测试失败"

# 测试Retrieval Service
echo -e "\n[3/5] 测试Retrieval Service..."
curl -X POST "$BASE_URL:8012/api/v1/retrieval/hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "top_k": 5,
    "tenant_id": "test_tenant"
  }' \
  -w "\nStatus: %{http_code}\n" || echo "❌ Retrieval测试失败"

# 测试Model Adapter
echo -e "\n[4/5] 测试Model Adapter..."
curl -X POST "$BASE_URL:8005/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }' \
  -w "\nStatus: %{http_code}\n" || echo "❌ Model Adapter测试失败"

# 测试Vector Store Adapter
echo -e "\n[5/5] 测试Vector Store Adapter..."
curl -X GET "$BASE_URL:8003/health" \
  -w "\nStatus: %{http_code}\n" || echo "❌ Vector Store Adapter测试失败"

echo -e "\n✅ 测试完成"

