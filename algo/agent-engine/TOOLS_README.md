# Agent Engine - 工具系统使用指南

> **功能状态**: ✅ 已实现
> **实现日期**: 2025-10-27
> **Sprint**: Sprint 2
> **版本**: v1.0.0

---

## 📋 目录

- [概述](#概述)
- [可用工具](#可用工具)
- [快速开始](#快速开始)
- [API 使用](#api-使用)
- [配置说明](#配置说明)
- [扩展工具](#扩展工具)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 📖 概述

Agent Engine 的工具系统提供了 5 个内置工具，支持动态注册和执行：

| 工具                | 功能       | 状态      |
| ------------------- | ---------- | --------- |
| 🔍 `search`         | 互联网搜索 | ✅ 已实现 |
| 📚 `knowledge_base` | 知识库查询 | ✅ 已实现 |
| 🌤️ `weather`        | 天气查询   | ✅ 已实现 |
| 🧮 `calculator`     | 数学计算   | ✅ 已实现 |
| ⏰ `current_time`   | 当前时间   | ✅ 已实现 |

---

## 🛠️ 可用工具

### 1. 搜索工具 (Search)

**功能**: 在互联网上搜索信息（基于 SerpAPI）

**参数**:

- `query` (必需): 搜索查询词
- `num_results` (可选): 返回结果数量（默认 5）

**示例**:

```python
{
    "tool_name": "search",
    "parameters": {
        "query": "2024年AI发展趋势",
        "num_results": 5
    }
}
```

**环境变量**:

```bash
SERPAPI_KEY=your_serpapi_key  # 从 https://serpapi.com 获取
```

**未配置时**: 返回模拟结果

---

### 2. 知识库工具 (Knowledge Base)

**功能**: 从企业知识库中检索信息（调用 RAG Engine）

**参数**:

- `query` (必需): 查询问题
- `knowledge_base_id` (可选): 知识库 ID（默认 "default"）
- `top_k` (可选): 返回文档数量（默认 3）

**示例**:

```python
{
    "tool_name": "knowledge_base",
    "parameters": {
        "query": "公司休假政策",
        "knowledge_base_id": "hr_docs",
        "top_k": 3
    }
}
```

**环境变量**:

```bash
RAG_SERVICE_URL=http://localhost:8006  # RAG Engine 地址
```

**未连接时**: 返回模拟结果

---

### 3. 天气工具 (Weather)

**功能**: 查询指定城市的实时天气信息（基于 OpenWeather API）

**参数**:

- `city` (必需): 城市名称（中文或英文）
- `country` (可选): 国家代码（默认 "CN"）

**示例**:

```python
{
    "tool_name": "weather",
    "parameters": {
        "city": "北京",
        "country": "CN"
    }
}
```

**环境变量**:

```bash
OPENWEATHER_API_KEY=your_openweather_key  # 从 https://openweathermap.org 获取
```

**未配置时**: 返回模拟结果

---

### 4. 计算器工具 (Calculator)

**功能**: 执行安全的数学计算

**参数**:

- `expression` (必需): 数学表达式

**支持的运算**:

- 加减乘除: `+`, `-`, `*`, `/`
- 幂运算: `**`
- 取模: `%`
- 括号: `(`, `)`

**示例**:

```python
{
    "tool_name": "calculator",
    "parameters": {
        "expression": "(10 + 5) * 3 - 8 / 2"
    }
}
```

**安全性**: 使用 AST 安全求值，禁止任意代码执行

---

### 5. 当前时间工具 (Current Time)

**功能**: 获取当前日期和时间

**参数**:

- `timezone` (可选): 时区（默认 "Asia/Shanghai"）

**示例**:

```python
{
    "tool_name": "current_time",
    "parameters": {
        "timezone": "Asia/Shanghai"
    }
}
```

---

## 🚀 快速开始

### 1. 环境配置

创建 `.env` 文件：

```bash
# 必需配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
EMBEDDING_SERVICE_URL=http://localhost:8002

# 可选：真实搜索（推荐配置）
SERPAPI_KEY=your_serpapi_key

# 可选：真实天气
OPENWEATHER_API_KEY=your_openweather_key

# 可选：RAG Engine 连接
RAG_SERVICE_URL=http://localhost:8006
```

### 2. 启动服务

```bash
cd algo/agent-engine

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### 3. 访问 API 文档

打开浏览器访问: http://localhost:8003/docs

---

## 🌐 API 使用

### 列出所有工具

```bash
GET /api/v1/tools/list
```

**响应**:

```json
{
    "tools": [
        {
            "name": "search",
            "description": "在互联网上搜索信息...",
            "parameters": {...}
        },
        ...
    ],
    "count": 5
}
```

---

### 获取工具名称

```bash
GET /api/v1/tools/names
```

**响应**:

```json
{
  "tool_names": ["search", "knowledge_base", "weather", "calculator", "current_time"],
  "count": 5
}
```

---

### 获取工具定义（for LLM）

```bash
GET /api/v1/tools/definitions
```

**响应**: OpenAI Function Calling 格式的定义

---

### 执行工具

```bash
POST /api/v1/tools/execute
Content-Type: application/json

{
    "tool_name": "calculator",
    "parameters": {
        "expression": "2 ** 10"
    }
}
```

**响应**:

```json
{
  "tool_name": "calculator",
  "result": "2 ** 10 = 1024",
  "execution_time_ms": 5.2,
  "success": true
}
```

---

### 获取工具信息

```bash
GET /api/v1/tools/{tool_name}
```

---

### 重新加载工具

```bash
POST /api/v1/tools/reload
```

---

## ⚙️ 配置说明

### API Keys 配置

#### 1. SerpAPI（推荐）

免费额度: 100 次/月

注册地址: https://serpapi.com

```bash
export SERPAPI_KEY=your_serpapi_key
```

#### 2. OpenWeather API

免费额度: 1,000 次/天

注册地址: https://openweathermap.org/api

```bash
export OPENWEATHER_API_KEY=your_openweather_key
```

### RAG Engine 配置

确保 RAG Engine 正在运行：

```bash
# 默认地址
RAG_SERVICE_URL=http://localhost:8006
```

---

## 🔧 扩展工具

### 创建自定义工具

1. 创建工具类：

```python
# app/tools/custom_tools.py

class MyCustomTool:
    """自定义工具示例"""

    async def execute(self, param1: str, param2: int = 10) -> str:
        """
        执行工具

        Args:
            param1: 参数1
            param2: 参数2

        Returns:
            执行结果
        """
        # 你的工具逻辑
        return f"Result: {param1} with {param2}"

    def get_definition(self) -> dict:
        """获取工具定义（OpenAI Function Calling 格式）"""
        return {
            "name": "my_custom_tool",
            "description": "这是一个自定义工具的示例",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "参数1的描述"
                    },
                    "param2": {
                        "type": "integer",
                        "description": "参数2的描述（可选）",
                        "default": 10
                    }
                },
                "required": ["param1"]
            }
        }
```

2. 注册工具：

```python
from app.tools.dynamic_registry import get_tool_registry
from app.tools.custom_tools import MyCustomTool

tool_registry = get_tool_registry()
tool_registry.register(MyCustomTool())
```

---

## 💡 最佳实践

### 1. 工具选择

| 场景           | 推荐工具         |
| -------------- | ---------------- |
| 实时信息、新闻 | `search`         |
| 公司文档、政策 | `knowledge_base` |
| 天气查询       | `weather`        |
| 数学计算       | `calculator`     |
| 获取时间       | `current_time`   |

### 2. 错误处理

工具执行失败时，会返回错误信息而不抛出异常：

```json
{
  "tool_name": "search",
  "result": "搜索失败: HTTP 429",
  "execution_time_ms": 1234.5,
  "success": false
}
```

### 3. 超时设置

默认超时：

- 搜索工具: 10 秒
- 知识库工具: 30 秒
- 天气工具: 10 秒
- 计算器工具: 即时
- 时间工具: 即时

### 4. API Keys 管理

**推荐**: 使用环境变量管理敏感信息

```bash
# .env
SERPAPI_KEY=xxx
OPENWEATHER_API_KEY=xxx
```

**不推荐**: 硬编码 API Keys

---

## 🔍 故障排查

### 问题 1: 工具未找到

**错误**: `Tool 'xxx' not found`

**解决**:

1. 检查工具名称拼写
2. 调用 `GET /api/v1/tools/names` 查看可用工具
3. 尝试重新加载: `POST /api/v1/tools/reload`

---

### 问题 2: 搜索工具返回模拟结果

**症状**: 搜索结果包含 "注意: 这是模拟结果..."

**解决**: 配置 `SERPAPI_KEY` 环境变量

```bash
export SERPAPI_KEY=your_serpapi_key
```

---

### 问题 3: 知识库工具无法连接

**错误**: "RAG service not available"

**解决**:

1. 确认 RAG Engine 正在运行
2. 检查 `RAG_SERVICE_URL` 配置
3. 测试连接: `curl http://localhost:8006/health`

---

### 问题 4: 天气工具返回 HTTP 401

**原因**: API Key 无效或未配置

**解决**:

1. 检查 `OPENWEATHER_API_KEY` 是否正确
2. 验证 API Key: https://home.openweathermap.org/api_keys
3. 检查免费额度是否用尽

---

## 📊 性能指标

| 工具             | 平均延迟 | 成功率 | 备注                 |
| ---------------- | -------- | ------ | -------------------- |
| `search`         | ~500ms   | > 95%  | 依赖 SerpAPI 可用性  |
| `knowledge_base` | ~200ms   | > 90%  | 依赖 RAG Engine      |
| `weather`        | ~300ms   | > 95%  | 依赖 OpenWeather API |
| `calculator`     | < 5ms    | 100%   | 本地执行             |
| `current_time`   | < 1ms    | 100%   | 本地执行             |

---

## 📞 支持

**负责人**: AI Engineer
**问题反馈**: #sprint2-tools
**文档版本**: v1.0.0

---

## 🔗 相关链接

- [Agent Engine README](README.md)
- [Memory System README](MEMORY_SYSTEM_README.md)
- [SerpAPI Documentation](https://serpapi.com/docs)
- [OpenWeather API Documentation](https://openweathermap.org/api)

---

**最后更新**: 2025-10-27
**状态**: ✅ 已完成
