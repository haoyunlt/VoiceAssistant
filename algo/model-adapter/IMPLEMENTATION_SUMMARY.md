# Model Adapter 实现总结

## 服务概述

**Model Adapter**（模型适配器）是 VoiceHelper 平台的统一模型接口服务，负责适配和统一多个 AI 模型提供商的 API。

## 核心功能

### 1. 多提供商支持

- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Azure OpenAI**: GPT-4, GPT-35-turbo
- **Anthropic**: Claude-3 系列
- **智谱 AI**: GLM-4
- **通义千问**: Qwen-Max
- **百度文心**: ERNIE-Bot-4

### 2. 统一接口

- **Chat Completion**: 对话接口
- **Text Completion**: 文本补全
- **Embedding**: 文本向量化
- **Stream**: 流式响应支持

### 3. 自动路由

- 根据模型名称自动选择提供商
- 支持明确指定提供商
- 智能降级和容错

### 4. 协议转换

- 统一请求/响应格式
- 适配不同提供商的 API 差异
- 错误统一处理

## 技术架构

### 适配器模式

```
AdapterService (调度层)
    ├── OpenAIAdapter
    ├── AnthropicAdapter
    ├── ZhipuAdapter
    ├── QwenAdapter
    └── BaiduAdapter
```

### 核心类设计

#### BaseAdapter (抽象基类)

```python
class BaseAdapter(ABC):
    @abstractmethod
    async def chat(request: ChatRequest) -> ChatResponse
    @abstractmethod
    async def chat_stream(request: ChatRequest) -> AsyncIterator[str]
    @abstractmethod
    async def completion(request: CompletionRequest) -> CompletionResponse
    @abstractmethod
    async def completion_stream(request: CompletionRequest) -> AsyncIterator[str]
    @abstractmethod
    async def embedding(request: EmbeddingRequest) -> EmbeddingResponse
```

#### AdapterService (调度服务)

```python
class AdapterService:
    def _get_provider(model: str, provider: str) -> (str, BaseAdapter)
    async def chat(request: ChatRequest) -> ChatResponse
    async def chat_stream(request: ChatRequest) -> AsyncIterator[str]
    async def completion(request: CompletionRequest) -> CompletionResponse
    async def embedding(request: EmbeddingRequest) -> EmbeddingResponse
```

## 数据模型

### 请求模型

#### ChatRequest

```python
{
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "stream": false,
    "provider": "openai"  # 可选
}
```

#### EmbeddingRequest

```python
{
    "model": "text-embedding-3-small",
    "input": ["Hello world", "AI is amazing"],
    "provider": "openai"  # 可选
}
```

### 响应模型

#### ChatResponse

```python
{
    "id": "chatcmpl-xxx",
    "model": "gpt-4",
    "provider": "openai",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you?"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    },
    "created": 1234567890
}
```

## API 接口

### 聊天接口

```
POST /api/v1/chat/completions
```

### 补全接口

```
POST /api/v1/completion/create
```

### 向量化接口

```
POST /api/v1/embedding/create
```

### 模型列表

```
GET /api/v1/chat/models
```

## 路由策略

### 自动路由规则

1. **明确指定**: 优先使用 `provider` 参数
2. **前缀匹配**: 根据模型名称前缀判断
   - `gpt-*` → OpenAI
   - `claude-*` → Anthropic
   - `glm-*` → 智谱 AI
   - `qwen-*` → 通义千问
   - `ernie-*` → 百度文心
3. **默认路由**: 未匹配时使用 OpenAI

### 路由示例

```python
# 自动路由到 OpenAI
{"model": "gpt-4", "messages": [...]}

# 明确指定 Anthropic
{"model": "claude-3-opus", "provider": "anthropic", "messages": [...]}

# 跨提供商使用
{"model": "custom-model", "provider": "zhipu", "messages": [...]}
```

## 协议转换

### OpenAI → 标准格式

直接使用 OpenAI 格式作为标准格式。

### Anthropic → 标准格式

- 分离 `system` 消息
- 转换消息格式
- 映射 `stop_reason` → `finish_reason`
- 转换 usage 字段

## 流式响应

### SSE 格式

```
data: {"id":"xxx","choices":[{"delta":{"content":"Hello"}}]}

data: {"id":"xxx","choices":[{"delta":{"content":" world"}}]}

data: [DONE]
```

### 实现方式

```python
async def chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line + "\n\n"
```

## 错误处理

### 统一错误响应

```json
{
  "error": "provider_error",
  "detail": "OpenAI API request failed: Rate limit exceeded",
  "status_code": 429
}
```

### 错误类型

- `provider_error`: 提供商 API 错误
- `validation_error`: 请求参数错误
- `timeout_error`: 请求超时
- `not_implemented`: 功能未实现

## 性能优化

### 1. 异步处理

- 使用 httpx 异步客户端
- 非阻塞 I/O
- 并发请求支持

### 2. 连接管理

- 连接池复用
- Keep-Alive 连接
- 自动重连

### 3. 超时配置

- 连接超时：10 秒
- 读取超时：60 秒
- 总超时：60 秒（可配置）

## 配置管理

### 环境变量

- `OPENAI_API_KEY`: OpenAI API 密钥
- `ANTHROPIC_API_KEY`: Anthropic API 密钥
- `ZHIPU_API_KEY`: 智谱 AI API 密钥
- `QWEN_API_KEY`: 通义千问 API 密钥
- `BAIDU_API_KEY`: 百度文心 API 密钥
- `REQUEST_TIMEOUT`: 请求超时时间
- `MAX_RETRIES`: 最大重试次数

### 模型映射配置

```python
MODEL_MAPPINGS = {
    "gpt-4": "openai/gpt-4",
    "claude-3-opus": "anthropic/claude-3-opus-20240229",
    "glm-4": "zhipu/glm-4",
    ...
}
```

## 监控和日志

### 关键日志

```
Routing to openai for model gpt-4
OpenAI API request succeeded in 1.23s
Streaming from anthropic for model claude-3-opus
```

### 监控指标

- 请求总数（按提供商）
- 平均响应时间
- 错误率
- Token 消耗
- 提供商可用性

## 部署建议

### Docker 部署

```bash
docker build -t model-adapter .
docker run -p 8005:8005 model-adapter
```

### Kubernetes 部署

- HPA: CPU > 70% 自动扩容
- 资源限制: 1 CPU, 2GB Memory
- 健康检查: `/health`

## 后续改进

### 短期

- [ ] 完善国产模型适配器（智谱、千问、文心）
- [ ] 实现完整的流式支持
- [ ] 添加请求缓存
- [ ] 实现重试机制

### 中期

- [ ] 支持更多提供商（Google Gemini、Cohere）
- [ ] 智能降级和容错
- [ ] 成本优化和路由
- [ ] 负载均衡

### 长期

- [ ] 自动模型选择
- [ ] A/B 测试支持
- [ ] 性能基准对比
- [ ] 自动化测试

## 文档资源

- API 文档: http://localhost:8005/docs
- README: ./README.md
- 架构文档: ../../docs/arch/model-adapter.md

---

**实现日期**: 2025-10-26
**版本**: v1.0.0
**状态**: ✅ 完成
