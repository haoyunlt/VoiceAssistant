#!/bin/bash

# Model Router测试脚本

BASE_URL="http://localhost:8004"

echo "========================================="
echo "Model Router API 测试"
echo "========================================="
echo ""

# 1. 健康检查
echo "1. 健康检查"
curl -s "${BASE_URL}/health" | jq .
echo -e "\n"

# 2. 列出所有模型
echo "2. 列出所有可用模型"
curl -s "${BASE_URL}/api/v1/models" | jq .
echo -e "\n"

# 3. 获取特定模型信息
echo "3. 获取GPT-3.5模型信息"
curl -s "${BASE_URL}/api/v1/models/openai-gpt-3.5-turbo" | jq .
echo -e "\n"

# 4. 路由决策 - 最便宜的模型
echo "4. 路由决策 - 选择最便宜的模型"
curl -s -X POST "${BASE_URL}/api/v1/route" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain machine learning in simple terms",
    "max_tokens": 500,
    "strategy": "cheapest"
  }' | jq .
echo -e "\n"

# 5. 路由决策 - 最快的模型
echo "5. 路由决策 - 选择最快的模型"
curl -s -X POST "${BASE_URL}/api/v1/route" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France?",
    "max_tokens": 100,
    "strategy": "fastest"
  }' | jq .
echo -e "\n"

# 6. 路由决策 - 最佳质量
echo "6. 路由决策 - 选择最佳质量模型"
curl -s -X POST "${BASE_URL}/api/v1/route" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a complex algorithm explanation",
    "max_tokens": 1000,
    "strategy": "best_quality"
  }' | jq .
echo -e "\n"

# 7. 成本预测
echo "7. 预测GPT-4成本"
curl -s -X POST "${BASE_URL}/api/v1/cost/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "openai-gpt-4",
    "input_tokens": 1000,
    "output_tokens": 500
  }' | jq .
echo -e "\n"

# 8. 成本比较
echo "8. 比较多个模型的成本"
curl -s -X POST "${BASE_URL}/api/v1/cost/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "model_ids": [
      "openai-gpt-3.5-turbo",
      "openai-gpt-4",
      "claude-3-sonnet",
      "zhipu-glm-4"
    ],
    "input_tokens": 1000,
    "output_tokens": 500
  }' | jq .
echo -e "\n"

# 9. 记录使用情况
echo "9. 记录模型使用情况"
curl -s -X POST "${BASE_URL}/api/v1/usage" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "openai-gpt-3.5-turbo",
    "input_tokens": 100,
    "output_tokens": 50,
    "success": true,
    "latency": 450
  }' | jq .
echo -e "\n"

# 10. 查看使用统计
echo "10. 查看使用统计"
curl -s "${BASE_URL}/api/v1/usage/stats" | jq .
echo -e "\n"

# 11. 获取优化建议
echo "11. 获取成本优化建议"
curl -s "${BASE_URL}/api/v1/cost/recommendations" | jq .
echo -e "\n"

# 12. 查看熔断器状态
echo "12. 查看熔断器状态"
curl -s "${BASE_URL}/api/v1/circuit-breakers" | jq .
echo -e "\n"

echo "========================================="
echo "测试完成!"
echo "========================================="
