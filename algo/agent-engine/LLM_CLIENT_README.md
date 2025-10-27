# Agent Engine - LLM 客户端使用指南

> **功能状态**: ✅ 已实现
> **实现日期**: 2025-10-27
> **Sprint**: Sprint 3
> **版本**: v1.0.0

---

## 📖 概述

Agent Engine 现已集成多厂商 LLM 客户端，提供：

- **OpenAI** - GPT-4, GPT-3.5 Turbo
- **Claude** - Claude 3 (Opus, Sonnet, Haiku)
- **Ollama** - 本地 LLM (Llama 2, Mistral, 等)
- **自动降级** - OpenAI → Claude → Ollama

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/agent-engine
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# Ollama (本地，默认 http://localhost:11434)
export OLLAMA_BASE_URL="http://localhost:11434"

# 首选提供商
export PREFERRED_LLM_PROVIDER="openai"  # openai | claude | ollama
```

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

---

## 🎯 功能特性

### ✅ OpenAI GPT-4

- ✅ GPT-4 Turbo (128K context)
- ✅ GPT-3.5 Turbo (16K context)
- ✅ Function Calling
- ✅ 流式响应

### ✅ Claude 3

- ✅ Claude 3 Opus (最强大)
- ✅ Claude 3 Sonnet (平衡)
- ✅ Claude 3 Haiku (快速)
- ✅ 200K context window
- ✅ Tool Use

### ✅ Ollama (本地)

- ✅ Llama 2, Mistral, CodeLlama
- ✅ 完全离线运行
- ✅ 免费
- ✅ 私密

### ✅ 自动降级

**降级链**:

```
OpenAI → Claude → Ollama
```

---

## 🌐 API 端点

### 文本生成

**POST** `/api/v1/llm/complete`

**请求**:

```json
{
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Hello!" }
  ],
  "temperature": 0.7,
  "max_tokens": 2000,
  "provider": "openai",
  "stream": false
}
```

**响应**:

```json
{
  "content": "Hello! How can I help you today?",
  "model": "gpt-4-turbo-preview",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  },
  "provider": "openai"
}
```

### 流式生成

设置 `stream: true` 即可获得 SSE 流。

### 提供商状态

**GET** `/api/v1/llm/providers/status`

### 列出模型

**GET** `/api/v1/llm/models`

---

## 📚 Python API

```python
from app.llm.multi_llm_adapter import get_multi_llm_adapter
from app.llm.base import Message

# 获取适配器
adapter = get_multi_llm_adapter()

# 生成文本
messages = [
    Message(role="system", content="You are helpful."),
    Message(role="user", content="Hello!")
]

response, provider = await adapter.complete(
    messages=messages,
    temperature=0.7,
    max_tokens=2000
)

print(f"Provider: {provider}")
print(f"Response: {response.content}")
```

---

## 📊 性能对比

| 提供商        | 延迟   | 准确率   | 成本 | 备注         |
| ------------- | ------ | -------- | ---- | ------------ |
| OpenAI GPT-4  | ~1-3s  | **最高** | 付费 | 最强大       |
| Claude 3 Opus | ~2-4s  | **极高** | 付费 | 200K context |
| Ollama        | ~5-15s | 中等     | 免费 | 本地运行     |

---

## 🔧 配置

环境变量：

- `OPENAI_API_KEY` - OpenAI API 密钥
- `ANTHROPIC_API_KEY` - Claude API 密钥
- `OLLAMA_BASE_URL` - Ollama 服务地址
- `PREFERRED_LLM_PROVIDER` - 首选提供商

---

## 📞 支持

**负责人**: AI Engineer
**问题反馈**: #sprint3-llm
**文档版本**: v1.0.0

---

**最后更新**: 2025-10-27
**状态**: ✅ 已完成
