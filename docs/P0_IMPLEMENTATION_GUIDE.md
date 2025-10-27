# P0 任务实施指南

> 优先级：⚡ 最高
> 预计工期：2.5 人日
> 目标：统一 LLM 调用和向量存储访问

---

## ✅ P0-1: 统一 LLM 调用路径（2 人日）

### 目标

所有 AI 引擎服务必须通过`model-adapter`调用 LLM，禁止直连 OpenAI/Anthropic 等。

### 实施步骤

#### 第 1 步：创建统一 LLM 客户端（✅ 已完成）

已创建 `algo/common/llm_client.py` - 统一 LLM 调用客户端

**功能**:

- ✅ 通过 model-adapter 调用
- ✅ 支持 chat（非流式）
- ✅ 支持 chat_stream（流式）
- ✅ 支持 embedding
- ✅ 统一错误处理
- ✅ 配置化（环境变量）

**使用示例**:

```python
from common.llm_client import UnifiedLLMClient

# 初始化
client = UnifiedLLMClient(
    model_adapter_url="http://model-adapter:8005",
    default_model="gpt-3.5-turbo"
)

# 聊天
response = await client.chat(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7
)
print(response["content"])

# 生成（简化版）
text = await client.generate(prompt="What is RAG?")

# Embedding
embeddings = await client.create_embedding(["text1", "text2"])
```

---

#### 第 2 步：修改 RAG Engine（⏳ 进行中）

**需要修改的文件**:

1. **`algo/rag-engine/app/services/query_service.py`**

   - 删除：直接的 httpx 调用到 OpenAI
   - 改为：使用 UnifiedLLMClient

2. **`algo/rag-engine/app/services/generator_service.py`**

   - 删除：from openai import AsyncOpenAI
   - 改为：使用 UnifiedLLMClient

3. **`algo/rag-engine/app/core/rag_engine.py`**
   - 修改：llm_client 初始化逻辑

**修改示例**:

```python
# 修改前 ❌
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = await client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[...]
)

# 修改后 ✅
from common.llm_client import UnifiedLLMClient
client = UnifiedLLMClient()
response = await client.chat(
    messages=[...],
    model="gpt-3.5-turbo"
)
```

---

#### 第 3 步：修改 Agent Engine

**需要修改的文件**:

1. **`algo/agent-engine/app/services/llm_service.py`**

   ```python
   # 修改前
   async with httpx.AsyncClient(timeout=self.timeout) as client:
       response = await client.post(
           "https://api.openai.com/v1/chat/completions",
           ...
       )

   # 修改后
   from common.llm_client import UnifiedLLMClient
   llm_client = UnifiedLLMClient()
   response = await llm_client.chat(messages=[...])
   ```

2. **`algo/agent-engine/app/llm/ollama_client.py`**
   - 如果用于 Ollama 本地模型，保留
   - 如果用于 OpenAI，改为 UnifiedLLMClient

---

#### 第 4 步：修改 Multimodal Engine

**需要修改的文件**:

1. **`algo/multimodal-engine/app/core/vision_engine.py`**

   ```python
   # 修改前
   async with httpx.AsyncClient(timeout=30.0) as client:
       response = await client.post(
           "https://api.openai.com/v1/chat/completions",
           json={
               "model": "gpt-4-vision-preview",
               ...
           }
       )

   # 修改后
   from common.llm_client import UnifiedLLMClient
   vision_client = UnifiedLLMClient(default_model="gpt-4-vision-preview")
   response = await vision_client.chat(
       messages=[{
           "role": "user",
           "content": [
               {"type": "text", "text": "What's in this image?"},
               {"type": "image_url", "image_url": {"url": image_url}}
           ]
       }]
   )
   ```

---

#### 第 5 步：环境变量配置

在各服务的`.env`或`docker-compose.yml`中添加：

```bash
# Model Adapter配置
MODEL_ADAPTER_URL=http://model-adapter:8005
DEFAULT_LLM_MODEL=gpt-3.5-turbo

# 可选：如果model-adapter需要API key
# OPENAI_API_KEY=sk-xxx  # 只在model-adapter中配置
```

---

#### 第 6 步：验证与测试

**验证命令**:

```bash
# 1. 检查是否还有直连OpenAI的代码
cd /Users/lintao/important/ai-customer/VoiceAssistant
grep -r "from openai import" algo/rag-engine/ algo/agent-engine/ algo/multimodal-engine/

# 应该返回空，或只在废弃文件中

# 2. 检查是否还有直接调用openai.com的代码
grep -r "api.openai.com" algo/

# 应该返回空，或只在model-adapter中

# 3. 测试RAG Engine
cd algo/rag-engine
python -m pytest tests/test_llm_integration.py

# 4. 测试Agent Engine
cd algo/agent-engine
python -m pytest tests/test_llm_service.py
```

**集成测试**:

```bash
# 启动所有服务
docker-compose up -d model-adapter rag-engine agent-engine

# 测试RAG
curl -X POST http://localhost:8006/api/v1/rag/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "knowledge_base_id": "test_kb",
    "tenant_id": "test_tenant"
  }'

# 测试Agent
curl -X POST http://localhost:8003/api/v1/agent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Calculate 25 * 4 + 10",
    "tools": ["calculator"]
  }'
```

---

## ✅ P0-2: 统一向量存储访问（0.5 人日）

### 目标

所有服务必须通过`vector-store-adapter`访问向量数据库，禁止直连 Milvus。

### 实施步骤

#### 第 1 步：修改 Retrieval Service

**文件**: `algo/retrieval-service/app/infrastructure/vector_store_client.py`

```python
# 修改前 ❌
from pymilvus import connections, Collection

class VectorStoreClient:
    def __init__(self, host="localhost", port=19530):
        connections.connect(host=host, port=port)
        self.collection = Collection("document_chunks")

    def search(self, query_vector, top_k=10):
        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k
        )
        return results
```

```python
# 修改后 ✅
import httpx
import logging

logger = logging.getLogger(__name__)

class VectorStoreClient:
    """向量存储客户端 - 通过vector-store-adapter访问"""

    def __init__(
        self,
        adapter_url: str = "http://vector-store-adapter:8003",
        collection_name: str = "document_chunks",
        backend: str = "milvus",
        timeout: float = 30.0
    ):
        self.adapter_url = adapter_url.rstrip("/")
        self.collection_name = collection_name
        self.backend = backend
        self.timeout = timeout

        logger.info(
            f"VectorStoreClient initialized: {adapter_url}, "
            f"collection={collection_name}, backend={backend}"
        )

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        tenant_id: str = None,
        filters: dict = None
    ) -> list[dict]:
        """
        向量检索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            tenant_id: 租户ID（用于过滤）
            filters: 额外过滤条件

        Returns:
            检索结果列表
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.adapter_url}/collections/{self.collection_name}/search",
                    json={
                        "backend": self.backend,
                        "query_vector": query_vector,
                        "top_k": top_k,
                        "tenant_id": tenant_id,
                        "filters": filters
                    }
                )
                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Search returned {result.get('count', 0)} results "
                    f"via adapter service"
                )

                return result.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Vector search error: {e}")
            raise RuntimeError(f"Vector search failed: {e}")

    async def insert_batch(self, data_list: list[dict]):
        """批量插入向量"""
        if not data_list:
            logger.warning("Empty data list for insertion")
            return

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.adapter_url}/collections/{self.collection_name}/insert",
                    json={
                        "backend": self.backend,
                        "data": data_list
                    }
                )
                response.raise_for_status()
                result = response.json()

                logger.info(f"Inserted {len(data_list)} vectors via adapter service")
                return result

        except httpx.HTTPError as e:
            logger.error(f"Vector insert error: {e}")
            raise
```

---

#### 第 2 步：更新配置

**文件**: `algo/retrieval-service/.env`

```bash
# 修改前
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 修改后
VECTOR_STORE_ADAPTER_URL=http://vector-store-adapter:8003
VECTOR_COLLECTION_NAME=document_chunks
VECTOR_BACKEND=milvus  # 或 pgvector
```

---

#### 第 3 步：验证

```bash
# 1. 检查是否还有直连Milvus
cd /Users/lintao/important/ai-customer/VoiceAssistant
grep -r "from pymilvus import" algo/retrieval-service/
grep -r "connections.connect" algo/retrieval-service/

# 应该返回空

# 2. 测试retrieval-service
cd algo/retrieval-service
docker-compose up -d vector-store-adapter retrieval-service

# 3. 测试检索
curl -X POST http://localhost:8012/api/v1/retrieval/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "top_k": 5,
    "tenant_id": "test_tenant"
  }'
```

---

#### 第 4 步：网络隔离（可选但推荐）

在 K8s 中使用 NetworkPolicy 禁止直连 Milvus：

```yaml
# deployments/k8s/network-policy-milvus.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: milvus-access-control
  namespace: voiceassistant
spec:
  podSelector:
    matchLabels:
      app: milvus
  policyTypes:
    - Ingress
  ingress:
    # 只允许vector-store-adapter访问
    - from:
        - podSelector:
            matchLabels:
              app: vector-store-adapter
      ports:
        - protocol: TCP
          port: 19530
```

应用：

```bash
kubectl apply -f deployments/k8s/network-policy-milvus.yaml
```

---

## 📊 P0 完成检查清单

### 代码检查

- [ ] rag-engine 不再直连 OpenAI
- [ ] agent-engine 不再直连 OpenAI
- [ ] multimodal-engine 不再直连 OpenAI
- [ ] retrieval-service 不再直连 Milvus
- [ ] 所有服务都使用统一客户端
- [ ] 环境变量已配置

### 测试检查

- [ ] RAG Engine 集成测试通过
- [ ] Agent Engine 集成测试通过
- [ ] Retrieval Service 测试通过
- [ ] E2E 测试通过
- [ ] 性能测试无明显劣化

### 文档检查

- [ ] README 更新（调用方式）
- [ ] API 文档更新
- [ ] 环境变量文档更新
- [ ] 架构图更新

### 部署检查

- [ ] Docker 镜像重新构建
- [ ] 环境变量更新（K8s ConfigMap）
- [ ] 灰度发布计划制定
- [ ] 回滚方案准备

---

## 🚨 风险与缓解

### 风险 1：延迟增加

**影响**: 通过 adapter 可能增加 10-20ms 延迟
**缓解**:

- Adapter 做轻量级转发，无重逻辑
- 部署多副本，负载均衡
- 监控延迟，及时优化

### 风险 2：Adapter 单点故障

**影响**: Adapter 挂了所有 LLM 调用失败
**缓解**:

- 部署 3 个以上副本
- 增加健康检查和自动重启
- 设置熔断器（Circuit Breaker）
- 准备快速回滚方案

### 风险 3：兼容性问题

**影响**: 修改后可能出现接口不兼容
**缓解**:

- 充分的单元测试和集成测试
- 灰度发布，逐步切换
- 保留旧代码作为 fallback
- 监控错误率，异常立即回滚

---

## 📈 成功指标

### 技术指标

```yaml
- LLM调用规范性: 100%（无直连）
- 向量存储访问规范性: 100%（通过adapter）
- P95延迟: <520ms（增加<20ms）
- 错误率: <0.1%
- 测试覆盖率: >80
```

### 业务指标

```yaml
- RAG生成成功率: >99
- Agent执行成功率: >98
- Token成本追踪: 100%可见
- 模型切换时间: <2小时（from 2天）
```

---

## 📞 支持与联系

**遇到问题？**

- Slack 频道: #architecture-refactor
- 文档: docs/ARCHITECTURE_REVIEW.md
- 负责人: @架构组

**进度追踪**:

- 任务看板: [Jira/GitHub Projects]
- 日报: 每日站会
- 周报: 每周五发送

---

**创建时间**: 2025-10-27
**更新时间**: 2025-10-27
**状态**: 🔄 进行中
**负责人**: 待分配
