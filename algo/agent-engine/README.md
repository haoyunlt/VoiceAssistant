# Agent Engine - AI Agent 执行引擎

## 概述

Agent Engine 是 VoiceAssistant 平台的 AI Agent 执行引擎，负责：

- **Agent 任务执行**：基于 ReAct 模式的智能任务执行
- **工具调用**：管理和执行各种工具（计算器、搜索、知识库等）
- **推理链**：多步骤推理和决策
- **异步任务**：支持异步任务执行和状态查询

## 技术栈

- **FastAPI**: 现代化的 Python Web 框架
- **Python 3.11+**: 异步支持
- **OpenAI API**: LLM 调用
- **Pydantic**: 数据验证

## 目录结构

```
agent-engine/
├── main.py                 # FastAPI应用入口
├── app/
│   ├── core/              # 核心配置
│   │   ├── config.py      # 配置管理
│   │   └── logging_config.py  # 日志配置
│   ├── models/            # 数据模型
│   │   └── agent.py       # Agent相关模型
│   ├── routers/           # API路由
│   │   ├── health.py      # 健康检查
│   │   ├── agent.py       # Agent执行
│   │   └── tools.py       # 工具管理
│   └── services/          # 业务逻辑
│       ├── agent_service.py   # Agent执行服务
│       ├── llm_service.py     # LLM服务
│       └── tool_service.py    # 工具服务
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker镜像
├── Makefile              # 构建脚本
└── README.md             # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env`，设置 OpenAI API 密钥：

```
OPENAI_API_KEY=your-api-key-here
```

### 3. 启动服务

```bash
# 开发模式
make run

# 或直接使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

### 4. 访问 API 文档

打开浏览器访问：

- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

## API 端点

### 健康检查

```bash
GET /health
```

### 执行 Agent 任务

```bash
POST /api/v1/agent/execute
Content-Type: application/json

{
  "task": "What is 25 * 4 + 10?",
  "tools": ["calculator"],
  "max_iterations": 10
}
```

### 异步执行 Agent 任务

```bash
POST /api/v1/agent/execute-async
Content-Type: application/json

{
  "task": "Search for the latest news about AI",
  "tools": ["search", "knowledge_base"],
  "max_iterations": 10
}
```

返回：

```json
{
  "task_id": "task_abc123",
  "status": "pending"
}
```

### 查询任务状态

```bash
GET /api/v1/agent/task/{task_id}
```

### 列出所有工具

```bash
GET /api/v1/tools/list
```

### 执行工具

```bash
POST /api/v1/tools/{tool_name}/execute
Content-Type: application/json

{
  "expression": "10 + 20"
}
```

## ReAct 工作流程

Agent 使用**ReAct**（Reasoning + Acting）模式：

1. **Thought**：LLM 思考下一步行动
2. **Action**：决定使用哪个工具及参数
3. **Observation**：执行工具并观察结果
4. **重复**：直到找到最终答案或达到最大迭代次数

示例执行流程：

```
User: What is 25 * 4 + 10?

Iteration 1:
├─ Thought: "I need to calculate 25 * 4 + 10. I should use the calculator tool."
├─ Action: calculator
├─ Input: {"expression": "25 * 4 + 10"}
└─ Observation: "110"

Iteration 2:
├─ Thought: "The calculator returned 110. This is the final answer."
└─ Final Answer: "110"
```

## 内置工具

1. **calculator**: 数学计算

   - 参数: `expression` (string)
   - 示例: `"10 + 20 * 3"`

2. **search**: 互联网搜索（示例实现）

   - 参数: `query` (string)
   - 示例: `"latest AI news"`

3. **knowledge_base**: 知识库查询（示例实现）
   - 参数: `query` (string)
   - 示例: `"product documentation"`

## 扩展工具

要添加新工具，在 `ToolService` 中注册：

```python
self.register_tool(
    name="my_tool",
    description="Tool description",
    function=self._my_tool_function,
    parameters={
        "param1": {"type": "string", "description": "..."}
    },
    required_params=["param1"],
)
```

## Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
make docker-run
```

## 测试

```bash
# 运行测试
make test

# 代码检查
make lint

# 代码格式化
make format
```

## 配置说明

| 配置项            | 说明            | 默认值  |
| ----------------- | --------------- | ------- |
| `OPENAI_API_KEY`  | OpenAI API 密钥 | -       |
| `DEFAULT_MODEL`   | 默认 LLM 模型   | `gpt-4` |
| `MAX_ITERATIONS`  | 最大迭代次数    | `10`    |
| `TIMEOUT_SECONDS` | 超时时间（秒）  | `300`   |
| `PORT`            | 服务端口        | `8003`  |

## 监控指标

- 任务执行时间
- 迭代次数
- 工具调用次数
- 成功率/失败率
- Token 消耗

## 日志

日志输出格式：

```
2025-01-26 10:30:45 - agent_service - INFO - [task_abc123] Starting agent execution: What is...
2025-01-26 10:30:46 - agent_service - INFO - [task_abc123] Iteration 1/10
2025-01-26 10:30:46 - agent_service - INFO - [task_abc123] Thought: I need to calculate...
2025-01-26 10:30:46 - agent_service - INFO - [task_abc123] Action: calculator with {...}
2025-01-26 10:30:46 - agent_service - INFO - [task_abc123] Observation: 110
2025-01-26 10:30:47 - agent_service - INFO - [task_abc123] Completed in 1.23s
```

## 许可证

MIT License
