# Model Adapter 服务功能清单与迭代计划

## 服务概述

Model Adapter 是模型适配器服务，提供统一的 AI 模型调用接口，支持多个 LLM 提供商。

**技术栈**: FastAPI + Python 3.11+ + OpenAI SDK + Anthropic SDK

**端口**: 8005

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 核心适配器
- ✅ OpenAI 适配器（Chat、Completion、Embedding）
- ✅ Azure OpenAI 适配器
- ✅ Anthropic 适配器（部分）
- ✅ 统一接口抽象
- ✅ 流式响应支持（OpenAI）

#### 2. API 接口
- ✅ `/api/v1/chat/completions` - 聊天接口
- ✅ `/api/v1/completion/create` - 补全接口
- ✅ `/api/v1/embedding/create` - 向量化接口
- ✅ `/api/v1/chat/models` - 模型列表
- ✅ `/health` - 健康检查

#### 3. 基础设施
- ✅ FastAPI 框架
- ✅ Pydantic 数据模型
- ✅ 配置管理
- ✅ 日志系统

---

## 二、待完成功能清单

### 🔄 P0 - 国产模型适配（迭代1：2周）

#### 1. 智谱 AI (GLM) 适配器
**当前状态**: 部分实现，需完善

**位置**: `algo/model-adapter/app/services/providers/zhipu_adapter.py`

**待实现**:

```python
# 文件: algo/model-adapter/app/services/providers/zhipu_adapter.py

import zhipuai
from typing import AsyncIterator

class ZhipuAdapter(BaseAdapter):
    """智谱 AI 适配器"""
    
    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            raise ValueError("ZHIPU_API_KEY not configured")
        
        zhipuai.api_key = self.api_key
        self.client = zhipuai.ZhipuAI(api_key=self.api_key)
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        智谱 AI 聊天接口
        """
        try:
            # 转换消息格式
            messages = self._convert_messages(request.messages)
            
            # 调用智谱 API
            response = self.client.chat.completions.create(
                model=request.model or "glm-4",
                messages=messages,
                temperature=request.temperature or 0.95,
                top_p=request.top_p or 0.7,
                max_tokens=request.max_tokens or 2048,
                stream=False
            )
            
            # 转换响应格式
            return ChatResponse(
                id=response.id,
                model=response.model,
                choices=[
                    Choice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=response.choices[0].message.content
                        ),
                        finish_reason=response.choices[0].finish_reason
                    )
                ],
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            )
        
        except Exception as e:
            logger.error(f"Zhipu chat error: {e}")
            raise AdapterError(f"Zhipu API call failed: {str(e)}")
    
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        智谱 AI 流式聊天
        """
        try:
            messages = self._convert_messages(request.messages)
            
            # 流式调用
            response = self.client.chat.completions.create(
                model=request.model or "glm-4",
                messages=messages,
                temperature=request.temperature or 0.95,
                max_tokens=request.max_tokens or 2048,
                stream=True
            )
            
            # 流式返回
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield self._format_stream_chunk(
                        chunk_id=chunk.id,
                        content=chunk.choices[0].delta.content,
                        finish_reason=chunk.choices[0].finish_reason
                    )
        
        except Exception as e:
            logger.error(f"Zhipu stream error: {e}")
            raise AdapterError(f"Zhipu stream failed: {str(e)}")
    
    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        智谱 AI Embedding
        """
        try:
            # 调用智谱 Embedding API
            response = self.client.embeddings.create(
                model="embedding-2",
                input=request.input
            )
            
            return EmbeddingResponse(
                model="embedding-2",
                data=[
                    EmbeddingData(
                        embedding=item.embedding,
                        index=item.index
                    )
                    for item in response.data
                ],
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    total_tokens=response.usage.total_tokens
                )
            )
        
        except Exception as e:
            logger.error(f"Zhipu embedding error: {e}")
            raise AdapterError(f"Zhipu embedding failed: {str(e)}")
    
    def _convert_messages(self, messages: List[Message]) -> List[dict]:
        """转换消息格式"""
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]
```

**验收标准**:
- [ ] Chat 接口完成
- [ ] 流式接口完成
- [ ] Embedding 接口完成
- [ ] 错误处理完善

#### 2. 通义千问 (Qwen) 适配器
**当前状态**: 部分实现，需完善

**位置**: `algo/model-adapter/app/services/providers/qwen_adapter.py`

**待实现**:

```python
# 文件: algo/model-adapter/app/services/providers/qwen_adapter.py

import dashscope
from dashscope import Generation, TextEmbedding
from http import HTTPStatus

class QwenAdapter(BaseAdapter):
    """通义千问适配器"""
    
    def __init__(self):
        self.api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("QWEN_API_KEY not configured")
        
        dashscope.api_key = self.api_key
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        通义千问聊天接口
        """
        try:
            messages = self._convert_messages(request.messages)
            
            # 调用通义千问 API
            response = Generation.call(
                model=request.model or "qwen-max",
                messages=messages,
                result_format='message',
                temperature=request.temperature or 1.0,
                top_p=request.top_p or 0.8,
                max_tokens=request.max_tokens or 2000,
                stream=False
            )
            
            if response.status_code == HTTPStatus.OK:
                return ChatResponse(
                    id=response.request_id,
                    model=request.model or "qwen-max",
                    choices=[
                        Choice(
                            index=0,
                            message=Message(
                                role="assistant",
                                content=response.output.choices[0].message.content
                            ),
                            finish_reason=response.output.choices[0].finish_reason
                        )
                    ],
                    usage=Usage(
                        prompt_tokens=response.usage.input_tokens,
                        completion_tokens=response.usage.output_tokens,
                        total_tokens=response.usage.total_tokens
                    )
                )
            else:
                raise AdapterError(f"Qwen API error: {response.message}")
        
        except Exception as e:
            logger.error(f"Qwen chat error: {e}")
            raise AdapterError(f"Qwen API call failed: {str(e)}")
    
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        通义千问流式聊天
        """
        try:
            messages = self._convert_messages(request.messages)
            
            # 流式调用
            responses = Generation.call(
                model=request.model or "qwen-max",
                messages=messages,
                result_format='message',
                temperature=request.temperature or 1.0,
                max_tokens=request.max_tokens or 2000,
                stream=True,
                incremental_output=True
            )
            
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    content = response.output.choices[0].message.content
                    if content:
                        yield self._format_stream_chunk(
                            chunk_id=response.request_id,
                            content=content,
                            finish_reason=response.output.choices[0].finish_reason
                        )
                else:
                    raise AdapterError(f"Qwen stream error: {response.message}")
        
        except Exception as e:
            logger.error(f"Qwen stream error: {e}")
            raise AdapterError(f"Qwen stream failed: {str(e)}")
    
    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        通义千问 Embedding
        """
        try:
            # 调用通义千问 Embedding API
            response = TextEmbedding.call(
                model="text-embedding-v2",
                input=request.input
            )
            
            if response.status_code == HTTPStatus.OK:
                return EmbeddingResponse(
                    model="text-embedding-v2",
                    data=[
                        EmbeddingData(
                            embedding=item.embedding,
                            index=idx
                        )
                        for idx, item in enumerate(response.output.embeddings)
                    ],
                    usage=Usage(
                        prompt_tokens=response.usage.total_tokens,
                        total_tokens=response.usage.total_tokens
                    )
                )
            else:
                raise AdapterError(f"Qwen embedding error: {response.message}")
        
        except Exception as e:
            logger.error(f"Qwen embedding error: {e}")
            raise AdapterError(f"Qwen embedding failed: {str(e)}")
```

**验收标准**:
- [ ] Chat 接口完成
- [ ] 流式接口完成
- [ ] Embedding 接口完成
- [ ] 错误处理完善

#### 3. 百度文心 (ERNIE) 适配器
**当前状态**: 部分实现，需完善

**位置**: `algo/model-adapter/app/services/providers/baidu_adapter.py`

**待实现**:

```python
# 文件: algo/model-adapter/app/services/providers/baidu_adapter.py

import requests
import json

class BaiduAdapter(BaseAdapter):
    """百度文心适配器"""
    
    def __init__(self):
        self.api_key = os.getenv("BAIDU_API_KEY")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Baidu credentials not configured")
        
        self.access_token = None
        self.token_expires_at = 0
    
    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        import time
        
        # 检查是否需要刷新
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        # 获取新令牌
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        response = requests.post(url, params=params)
        result = response.json()
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            self.token_expires_at = time.time() + result.get("expires_in", 2592000) - 300
            return self.access_token
        else:
            raise AdapterError(f"Failed to get access token: {result}")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        百度文心聊天接口
        """
        try:
            access_token = await self._get_access_token()
            
            # 选择模型端点
            model_map = {
                "ernie-bot": "completions",
                "ernie-bot-4": "completions_pro",
                "ernie-bot-turbo": "eb-instant"
            }
            model_name = request.model or "ernie-bot"
            endpoint = model_map.get(model_name, "completions")
            
            url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{endpoint}"
            
            # 构建请求
            messages = self._convert_messages(request.messages)
            
            payload = {
                "messages": messages,
                "temperature": request.temperature or 0.95,
                "top_p": request.top_p or 0.8,
                "max_output_tokens": request.max_tokens or 2048,
                "stream": False
            }
            
            # 调用 API
            response = requests.post(
                url,
                params={"access_token": access_token},
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            
            if "error_code" in result:
                raise AdapterError(f"Baidu API error: {result}")
            
            return ChatResponse(
                id=result.get("id", ""),
                model=model_name,
                choices=[
                    Choice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=result["result"]
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=result["usage"]["prompt_tokens"],
                    completion_tokens=result["usage"]["completion_tokens"],
                    total_tokens=result["usage"]["total_tokens"]
                )
            )
        
        except Exception as e:
            logger.error(f"Baidu chat error: {e}")
            raise AdapterError(f"Baidu API call failed: {str(e)}")
    
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        百度文心流式聊天
        """
        try:
            access_token = await self._get_access_token()
            
            model_name = request.model or "ernie-bot"
            endpoint = "completions"
            url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{endpoint}"
            
            messages = self._convert_messages(request.messages)
            
            payload = {
                "messages": messages,
                "temperature": request.temperature or 0.95,
                "max_output_tokens": request.max_tokens or 2048,
                "stream": True
            }
            
            # 流式请求
            response = requests.post(
                url,
                params={"access_token": access_token},
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        data = json.loads(line_text[6:])
                        
                        if "result" in data:
                            yield self._format_stream_chunk(
                                chunk_id=data.get("id", ""),
                                content=data["result"],
                                finish_reason=data.get("is_end", False) and "stop" or None
                            )
        
        except Exception as e:
            logger.error(f"Baidu stream error: {e}")
            raise AdapterError(f"Baidu stream failed: {str(e)}")
    
    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        百度文心 Embedding
        """
        try:
            access_token = await self._get_access_token()
            
            url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/embeddings/embedding-v1"
            
            # 处理输入
            texts = request.input if isinstance(request.input, list) else [request.input]
            
            payload = {"input": texts}
            
            response = requests.post(
                url,
                params={"access_token": access_token},
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            
            if "error_code" in result:
                raise AdapterError(f"Baidu embedding error: {result}")
            
            return EmbeddingResponse(
                model="embedding-v1",
                data=[
                    EmbeddingData(
                        embedding=item["embedding"],
                        index=item["index"]
                    )
                    for item in result["data"]
                ],
                usage=Usage(
                    prompt_tokens=result["usage"]["prompt_tokens"],
                    total_tokens=result["usage"]["total_tokens"]
                )
            )
        
        except Exception as e:
            logger.error(f"Baidu embedding error: {e}")
            raise AdapterError(f"Baidu embedding failed: {str(e)}")
```

**验收标准**:
- [ ] Chat 接口完成
- [ ] 流式接口完成
- [ ] Embedding 接口完成
- [ ] Token 管理完善

---

### 🔄 P1 - 高级功能（迭代2：1周）

#### 1. 模型路由增强

```python
# 文件: algo/model-adapter/app/services/adapter_service.py

class AdapterService:
    """适配器服务 - 智能路由"""
    
    def __init__(self):
        self.adapters = {
            "openai": OpenAIAdapter(),
            "azure": AzureOpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
            "zhipu": ZhipuAdapter(),
            "qwen": QwenAdapter(),
            "baidu": BaiduAdapter()
        }
        
        self.model_mapping = self._load_model_mapping()
    
    def _load_model_mapping(self) -> dict:
        """加载模型映射配置"""
        return {
            # OpenAI
            "gpt-4": "openai",
            "gpt-4-turbo": "openai",
            "gpt-3.5-turbo": "openai",
            
            # Anthropic
            "claude-3-opus": "anthropic",
            "claude-3-sonnet": "anthropic",
            
            # 智谱
            "glm-4": "zhipu",
            "glm-3-turbo": "zhipu",
            
            # 千问
            "qwen-max": "qwen",
            "qwen-turbo": "qwen",
            
            # 文心
            "ernie-bot-4": "baidu",
            "ernie-bot": "baidu"
        }
    
    async def route_chat(self, request: ChatRequest) -> ChatResponse:
        """
        智能路由聊天请求
        """
        # 1. 确定提供商
        provider = self._determine_provider(request)
        
        # 2. 获取适配器
        adapter = self.adapters.get(provider)
        if not adapter:
            raise ValueError(f"Provider {provider} not supported")
        
        # 3. 执行请求（带重试和降级）
        try:
            return await self._execute_with_retry(
                adapter.chat,
                request
            )
        except Exception as e:
            # 降级到备用模型
            if fallback := self._get_fallback_provider(provider):
                logger.warning(f"Fallback to {fallback} due to {e}")
                return await self.adapters[fallback].chat(request)
            raise
    
    def _determine_provider(self, request: ChatRequest) -> str:
        """确定提供商"""
        # 明确指定
        if request.provider:
            return request.provider
        
        # 根据模型名称
        if request.model in self.model_mapping:
            return self.model_mapping[request.model]
        
        # 默认
        return "openai"
    
    async def _execute_with_retry(
        self,
        func,
        request,
        max_retries: int = 3
    ):
        """带重试的执行"""
        for attempt in range(max_retries):
            try:
                return await func(request)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = 2 ** attempt
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
                await asyncio.sleep(wait_time)
```

**验收标准**:
- [ ] 智能路由完成
- [ ] 重试机制完善
- [ ] 降级策略实现

#### 2. 性能优化

```python
# 文件: algo/model-adapter/app/services/cache_service.py

import hashlib
import redis
import json

class CacheService:
    """LLM 响应缓存服务"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=1,
            decode_responses=True
        )
        self.ttl = 3600  # 1小时
    
    def get_cache_key(self, request: ChatRequest) -> str:
        """生成缓存键"""
        # 使用请求内容生成唯一键
        key_data = {
            "model": request.model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"llm_cache:{hash_key}"
    
    async def get_cached_response(
        self,
        request: ChatRequest
    ) -> Optional[ChatResponse]:
        """获取缓存的响应"""
        cache_key = self.get_cache_key(request)
        
        cached = self.redis_client.get(cache_key)
        if cached:
            logger.info(f"Cache hit: {cache_key}")
            return ChatResponse.parse_raw(cached)
        
        return None
    
    async def cache_response(
        self,
        request: ChatRequest,
        response: ChatResponse
    ):
        """缓存响应"""
        cache_key = self.get_cache_key(request)
        
        self.redis_client.setex(
            cache_key,
            self.ttl,
            response.json()
        )
        
        logger.info(f"Cached response: {cache_key}")
```

**验收标准**:
- [ ] 响应缓存实现
- [ ] 缓存命中率 > 30%
- [ ] 延迟降低 50%

#### 3. 可观测性

```python
# 文件: algo/model-adapter/app/middleware/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# 定义指标
request_counter = Counter(
    'model_adapter_requests_total',
    'Total requests',
    ['provider', 'model', 'status']
)

request_duration = Histogram(
    'model_adapter_request_duration_seconds',
    'Request duration',
    ['provider', 'model']
)

token_usage = Counter(
    'model_adapter_tokens_total',
    'Token usage',
    ['provider', 'model', 'type']
)

active_requests = Gauge(
    'model_adapter_active_requests',
    'Active requests',
    ['provider']
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """指标中间件"""
    start_time = time.time()
    
    # 增加活跃请求
    provider = request.headers.get("X-Provider", "unknown")
    active_requests.labels(provider=provider).inc()
    
    try:
        response = await call_next(request)
        
        # 记录指标
        duration = time.time() - start_time
        request_duration.labels(
            provider=provider,
            model=request.headers.get("X-Model", "unknown")
        ).observe(duration)
        
        request_counter.labels(
            provider=provider,
            model=request.headers.get("X-Model", "unknown"),
            status="success"
        ).inc()
        
        return response
    
    except Exception as e:
        request_counter.labels(
            provider=provider,
            model=request.headers.get("X-Model", "unknown"),
            status="error"
        ).inc()
        raise
    
    finally:
        active_requests.labels(provider=provider).dec()
```

**验收标准**:
- [ ] Prometheus 指标完成
- [ ] Grafana 仪表盘
- [ ] 告警规则配置

---

## 三、详细实施方案

### 阶段1：国产模型适配（Week 1-2）

#### Day 1-5: 智谱 AI
1. 实现 Chat 接口
2. 实现流式接口
3. 实现 Embedding
4. 测试

#### Day 6-10: 通义千问和文心
1. 实现通义千问适配器
2. 实现百度文心适配器
3. 集成测试

#### Day 11-14: 集成和优化
1. 模型路由增强
2. 错误处理
3. 文档

### 阶段2：高级功能（Week 3）

#### Day 15-17: 缓存和性能
1. 实现响应缓存
2. 性能优化
3. 测试

#### Day 18-21: 可观测性
1. Prometheus 指标
2. Grafana 仪表盘
3. 告警配置

---

## 四、验收标准

### 功能验收
- [ ] 所有适配器完成
- [ ] 流式响应正常
- [ ] Embedding 正常
- [ ] 缓存正常工作

### 性能验收
- [ ] P95 延迟 < 2s
- [ ] 缓存命中率 > 30%
- [ ] 支持 100 并发

### 质量验收
- [ ] 单元测试覆盖率 > 70%
- [ ] 所有 TODO 清理
- [ ] API 文档完整

---

## 总结

Model Adapter 的主要待完成功能：

1. **智谱 AI 适配器**: 完整实现 GLM-4
2. **通义千问适配器**: 完整实现 Qwen
3. **百度文心适配器**: 完整实现 ERNIE
4. **智能路由**: 自动选择和降级
5. **性能优化**: 缓存和指标

完成后将支持主流国产 LLM，提供统一接口。


