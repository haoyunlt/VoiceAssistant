# Model Adapter - 模型适配器服务

## 概述

Model Adapter 是 VoiceHelper 平台的模型适配器服务，负责：

- **统一接口**：提供统一的 AI 模型调用接口
- **多提供商支持**：OpenAI、Anthropic、智谱、千问、文心等
- **协议转换**：适配不同提供商的 API 协议
- **自动路由**：根据模型名称自动选择提供商
- **流式支持**：统一的流式响应接口
- **Embedding**：统一的向量化接口

## 技术栈

- **FastAPI**: Python Web 框架
- **httpx**: 异步 HTTP 客户端
- **Pydantic**: 数据验证
- **官方 SDK**: OpenAI、Anthropic SDK

## 支持的提供商

| 提供商          | Chat | Completion | Embedding | 流式 | 状态   |
| --------------- | ---- | ---------- | --------- | ---- | ------ |
| OpenAI          | ✅   | ✅         | ✅        | ✅   | 完成   |
| Azure OpenAI    | ✅   | ✅         | ✅        | ✅   | 完成   |
| Anthropic       | ✅   | ✅         | ❌        | 🔄   | 部分   |
| 智谱 AI (GLM)   | 🔄   | 🔄         | 🔄        | 🔄   | 待实现 |
| 通义千问 (Qwen) | 🔄   | 🔄         | 🔄        | 🔄   | 待实现 |
| 百度文心        | 🔄   | 🔄         | 🔄        | 🔄   | 待实现 |

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

配置 API 密钥：

```env
# OpenAI
OPENAI_API_KEY=sk-xxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# 智谱AI
ZHIPU_API_KEY=xxx

# 通义千问
QWEN_API_KEY=xxx

# 百度文心
BAIDU_API_KEY=xxx
BAIDU_SECRET_KEY=xxx
```

### 3. 启动服务

```bash
# 开发模式
make run

# 或直接使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8005
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc

## API 端点

### 聊天接口

```bash
POST /api/v1/chat/completions
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

### 补全接口

```bash
POST /api/v1/completion/create
Content-Type: application/json

{
  "model": "gpt-3.5-turbo",
  "prompt": "Write a poem about AI",
  "temperature": 0.7,
  "max_tokens": 500
}
```

### 向量化接口

```bash
POST /api/v1/embedding/create
Content-Type: application/json

{
  "model": "text-embedding-3-small",
  "input": ["Hello world", "AI is amazing"]
}
```

### 列出模型

```bash
GET /api/v1/chat/models
```

## 模型映射

服务会根据模型名称自动路由到对应的提供商：

| 模型名称          | 提供商    | 实际模型                 |
| ----------------- | --------- | ------------------------ |
| `gpt-4`           | OpenAI    | gpt-4                    |
| `gpt-3.5-turbo`   | OpenAI    | gpt-3.5-turbo            |
| `claude-3-opus`   | Anthropic | claude-3-opus-20240229   |
| `claude-3-sonnet` | Anthropic | claude-3-sonnet-20240229 |
| `glm-4`           | 智谱 AI   | glm-4                    |
| `qwen-max`        | 通义千问  | qwen-max                 |
| `ernie-bot`       | 百度文心  | ERNIE-Bot-4              |

也可以通过 `provider` 参数明确指定提供商：

```json
{
  "model": "gpt-4",
  "provider": "openai",
  "messages": [...]
}
```

## 流式响应

### 聊天流式

```bash
POST /api/v1/chat/completions
Content-Type: application/json

{
  "model": "gpt-3.5-turbo",
  "messages": [{"role": "user", "content": "Tell me a story"}],
  "stream": true
}
```

响应格式（SSE）：

```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"Once"}}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":" upon"}}]}

data: [DONE]
```

## 架构设计

### 分层结构

```
├── API层 (Routers)
│   ├── chat.py          # 聊天接口
│   ├── completion.py    # 补全接口
│   └── embedding.py     # 向量化接口
│
├── 服务层 (Services)
│   ├── adapter_service.py  # 适配器调度
│   └── providers/          # 各提供商适配器
│       ├── base_adapter.py
│       ├── openai_adapter.py
│       ├── anthropic_adapter.py
│       ├── zhipu_adapter.py
│       ├── qwen_adapter.py
│       └── baidu_adapter.py
│
├── 模型层 (Models)
│   ├── request.py       # 请求模型
│   └── response.py      # 响应模型
│
└── 核心层 (Core)
    ├── config.py        # 配置管理
    └── logging_config.py # 日志配置
```

### 适配器模式

每个提供商实现 `BaseAdapter` 接口：

```python
class BaseAdapter(ABC):
    async def chat(request) -> ChatResponse
    async def chat_stream(request) -> AsyncIterator[str]
    async def completion(request) -> CompletionResponse
    async def completion_stream(request) -> AsyncIterator[str]
    async def embedding(request) -> EmbeddingResponse
```

### 自动路由

`AdapterService` 根据模型名称自动选择适配器：

1. 检查是否明确指定 `provider`
2. 根据模型名称前缀判断（如 `gpt-` → OpenAI）
3. 默认使用 OpenAI

## 错误处理

统一的错误响应格式：

```json
{
  "error": "Error type",
  "detail": "Detailed error message",
  "status_code": 500
}
```

## 性能优化

### 1. 连接复用

- 使用 httpx 异步客户端
- 连接池管理
- Keep-Alive 连接

### 2. 超时控制

- 请求超时：60 秒（可配置）
- 连接超时：10 秒
- 读取超时：60 秒

### 3. 重试机制

- 最大重试次数：3 次
- 重试延迟：1 秒
- 指数退避

## 监控指标

- 请求总数（按提供商）
- 请求延迟（P50/P95/P99）
- 错误率
- Token 消耗统计
- 提供商可用性

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

## 许可证

MIT License
