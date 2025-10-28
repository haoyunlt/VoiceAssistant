# VoiceHelper - 19 - 最佳实践与实战案例

## 概述

本文档汇总了 VoiceHelper 平台在实际开发和生产环境中的最佳实践、实战经验和具体案例。这些实践经过验证，可以显著提升系统性能、稳定性和用户体验。

## 框架使用示例

### 1. 快速开始：创建对话并发送消息

**场景说明**

最基本的使用场景：创建一个对话会话，发送用户消息，接收 AI 回复。

**完整代码示例**

```python
import requests
import json

# 配置
BASE_URL = "http://api.voiceassistant.com"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 步骤 1: 创建对话
def create_conversation(user_id, tenant_id, title):
    response = requests.post(
        f"{BASE_URL}/api/v1/conversations",
        headers=headers,
        json={
            "user_id": user_id,
            "tenant_id": tenant_id,
            "title": title,
            "mode": "text"
        }
    )
    response.raise_for_status()
    return response.json()

# 步骤 2: 发送消息
def send_message(conversation_id, user_id, content):
    response = requests.post(
        f"{BASE_URL}/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "user_id": user_id,
            "role": "user",
            "content": content
        }
    )
    response.raise_for_status()
    return response.json()

# 步骤 3: 获取AI回复（调用AI Orchestrator）
def get_ai_response(conversation_id, user_message):
    response = requests.post(
        f"{BASE_URL}/api/v1/ai/chat",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": user_message,
            "mode": "auto"  # 自动选择模式
        }
    )
    response.raise_for_status()
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 创建对话
    conv = create_conversation(
        user_id="user_123",
        tenant_id="tenant_abc",
        title="产品咨询"
    )
    print(f"对话创建成功: {conv['id']}")

    # 发送用户消息
    user_msg = send_message(
        conversation_id=conv['id'],
        user_id="user_123",
        content="你好，请介绍一下VoiceHelper的主要功能"
    )
    print(f"用户消息: {user_msg['content']}")

    # 获取AI回复
    ai_response = get_ai_response(
        conversation_id=conv['id'],
        user_message="你好，请介绍一下VoiceHelper的主要功能"
    )
    print(f"AI回复: {ai_response['reply']}")
    print(f"引用来源: {len(ai_response.get('citations', []))} 条")
```

**关键要点**

1. **JWT 认证**：所有 API 调用都需要在 Header 中携带有效的 JWT Token
2. **错误处理**：使用 `response.raise_for_status()` 检查 HTTP 错误
3. **对话模式**：text/voice/video，根据场景选择
4. **AI 模式**：auto 让系统自动选择，也可以指定 rag/agent/chat

---

### 2. 流式对话：实时显示 AI 回复

**场景说明**

用户发送消息后，实时逐字显示 AI 生成的回复内容，提升用户体验。

**完整代码示例**

```python
import requests
import json
import sys

BASE_URL = "http://api.voiceassistant.com"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def stream_chat(conversation_id, message):
    """流式对话"""
    url = f"{BASE_URL}/api/v1/ai/chat/stream"

    response = requests.post(
        url,
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "message": message,
            "mode": "auto",
            "stream": True
        },
        stream=True  # 启用流式接收
    )

    print("AI回复: ", end="", flush=True)

    full_response = ""
    citations = []

    # 逐行读取流式响应
    for line in response.iter_lines():
        if not line:
            continue

        # 解析 Server-Sent Events 格式
        if line.startswith(b"data: "):
            data_str = line[6:].decode('utf-8')

            # 检查是否是结束标记
            if data_str.strip() == "[DONE]":
                print()  # 换行
                break

            try:
                data = json.loads(data_str)

                # 处理不同类型的事件
                if data.get("type") == "delta":
                    # 内容增量
                    delta = data.get("delta", "")
                    print(delta, end="", flush=True)
                    full_response += delta

                elif data.get("type") == "citation":
                    # 引用来源
                    citations.append(data)

                elif data.get("type") == "metadata":
                    # 元数据（Token使用、耗时等）
                    metadata = data.get("metadata", {})
                    print(f"\n\n---")
                    print(f"Token使用: {metadata.get('tokens_used', 0)}")
                    print(f"处理时间: {metadata.get('duration_ms', 0)}ms")

            except json.JSONDecodeError:
                continue

    # 显示引用来源
    if citations:
        print(f"\n引用来源 ({len(citations)}):")
        for i, cite in enumerate(citations, 1):
            print(f"  [{i}] {cite.get('title', 'Unknown')} (相似度: {cite.get('score', 0):.2f})")

    return full_response, citations

# 使用示例
if __name__ == "__main__":
    conversation_id = "conv_123456"
    user_message = "请详细介绍RAG技术的工作原理和优势"

    response, citations = stream_chat(conversation_id, user_message)
    print(f"\n\n完整回复长度: {len(response)} 字符")
```

**关键要点**

1. **Server-Sent Events**：使用 SSE 协议实现服务器推送
2. **实时显示**：使用 `flush=True` 强制刷新输出缓冲区
3. **多类型事件**：delta（内容）、citation（引用）、metadata（元数据）
4. **结束标记**：`[DONE]` 表示流式传输完成
5. **异常处理**：捕获 JSON 解析错误，避免单个事件失败影响整体

---

### 3. Agent 模式：执行复杂任务

**场景说明**

使用 Agent 引擎执行需要多步骤、多工具调用的复杂任务。

**完整代码示例**

```python
import requests
import json
import time

BASE_URL = "http://localhost:8003"  # Agent Engine 端点

def execute_agent_task(task, mode="react", max_steps=10, stream=True):
    """执行Agent任务"""
    url = f"{BASE_URL}/execute{'_stream' if stream else ''}"

    payload = {
        "task": task,
        "mode": mode,
        "max_steps": max_steps,
        "tools": None,  # None表示使用所有可用工具
        "conversation_id": f"conv_{int(time.time())}"
    }

    if stream:
        # 流式执行
        response = requests.post(url, json=payload, stream=True)

        print("=" * 60)
        print(f"任务: {task}")
        print("=" * 60)

        for line in response.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue

            event_str = line[6:].decode('utf-8')
            event = json.loads(event_str)

            event_type = event.get("type")

            if event_type == "step_start":
                print(f"\n>>> 步骤 {event['step']} 开始")

            elif event_type == "thought":
                print(f"💭 思考: {event['content']}")

            elif event_type == "action":
                print(f"🔧 动作: {event['action']}")
                print(f"   输入: {event['input']}")

            elif event_type == "observation":
                print(f"👁️  观察: {event['content']}")

            elif event_type == "final":
                print(f"\n✅ 最终答案:")
                print(f"   {event['content']}")

            elif event_type == "done":
                print(f"\n⏱️  执行完成，耗时: {event['execution_time']:.2f}s")

            elif event_type == "error":
                print(f"\n❌ 错误: {event['content']}")

        print("=" * 60)

    else:
        # 非流式执行
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        print("=" * 60)
        print(f"任务: {task}")
        print(f"模式: {result['mode']}")
        print(f"状态: {result['status']}")
        print(f"步骤数: {result['step_count']}")
        print(f"工具调用次数: {result['tool_call_count']}")
        print(f"执行时间: {result['execution_time']:.2f}s")
        print("=" * 60)

        # 显示每个步骤
        for step in result['steps']:
            print(f"\n步骤 {step['step']}:")
            print(f"  思考: {step['thought']}")
            if 'action' in step:
                print(f"  动作: {step['action']}")
                print(f"  输入: {step['action_input']}")
                print(f"  观察: {step['observation']}")
            if 'final_answer' in step:
                print(f"  最终答案: {step['final_answer']}")

        print("=" * 60)

        return result

# 使用示例
if __name__ == "__main__":
    # 示例1: 简单任务（计算）
    execute_agent_task(
        task="计算 (123 + 456) * 789 的结果",
        mode="react",
        max_steps=3,
        stream=True
    )

    # 示例2: 复杂任务（查询+发送）
    execute_agent_task(
        task="查询北京明天的天气预报，如果有雨就提醒我带伞",
        mode="react",
        max_steps=10,
        stream=True
    )

    # 示例3: Plan-Execute模式
    execute_agent_task(
        task="""
        帮我完成以下任务:
        1. 从知识库中搜索关于VoiceHelper的介绍
        2. 总结其核心功能（不超过200字）
        3. 生成一份产品宣传文案
        """,
        mode="plan_execute",
        max_steps=20,
        stream=False  # 使用非流式查看完整执行计划
    )
```

**关键要点**

1. **模式选择**：

   - `react`：适合需要工具调用的任务
   - `plan_execute`：适合多步骤复杂任务
   - `reflexion`：需要反思和改进的任务

2. **工具限制**：通过 `tools` 参数限制可用工具，提高安全性

3. **最大步骤数**：设置合理的 `max_steps` 避免无限循环

4. **流式 vs 非流式**：
   - 流式：实时反馈，用户体验好
   - 非流式：获取完整结果，便于分析

---

### 4. 文档上传与 RAG 检索

**场景说明**

上传知识库文档，然后使用 RAG 检索进行问答。

**完整代码示例**

```python
import requests
import time
import os

BASE_URL = "http://api.voiceassistant.com"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# 步骤1: 创建知识库集合
def create_collection(user_id, tenant_id, name, description):
    response = requests.post(
        f"{BASE_URL}/api/v1/knowledge/collections",
        headers=headers,
        json={
            "user_id": user_id,
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "type": "personal"
        }
    )
    response.raise_for_status()
    return response.json()

# 步骤2: 上传文档
def upload_document(collection_id, user_id, tenant_id, file_path):
    with open(file_path, 'rb') as f:
        files = {
            'file': (os.path.basename(file_path), f, 'application/pdf')
        }
        data = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'collection_id': collection_id,
            'metadata': '{}'
        }

        response = requests.post(
            f"{BASE_URL}/api/v1/knowledge/documents",
            headers={'Authorization': headers['Authorization']},
            files=files,
            data=data
        )
        response.raise_for_status()
        return response.json()

# 步骤3: 等待文档索引完成
def wait_for_indexing(document_id, timeout=300):
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = requests.get(
            f"{BASE_URL}/api/v1/knowledge/documents/{document_id}",
            headers=headers
        )
        response.raise_for_status()
        doc = response.json()

        status = doc.get('status')
        print(f"文档状态: {status}")

        if status == 'READY':
            print("索引完成!")
            return True
        elif status == 'FAILED':
            print("索引失败!")
            return False

        time.sleep(5)  # 等待5秒后重试

    print("索引超时!")
    return False

# 步骤4: RAG检索问答
def rag_query(collection_ids, query, user_id, top_k=5):
    response = requests.post(
        f"{BASE_URL}/api/v1/ai/rag/query",
        headers=headers,
        json={
            "query": query,
            "user_id": user_id,
            "knowledge_base_ids": collection_ids,
            "top_k": top_k,
            "enable_rerank": True,
            "retrieval_mode": "hybrid"  # 混合检索
        }
    )
    response.raise_for_status()
    return response.json()

# 使用示例
if __name__ == "__main__":
    user_id = "user_123"
    tenant_id = "tenant_abc"

    # 创建知识库
    collection = create_collection(
        user_id=user_id,
        tenant_id=tenant_id,
        name="产品文档",
        description="VoiceHelper产品相关文档"
    )
    print(f"知识库创建成功: {collection['id']}")

    # 上传文档
    doc = upload_document(
        collection_id=collection['id'],
        user_id=user_id,
        tenant_id=tenant_id,
        file_path="./docs/product_manual.pdf"
    )
    print(f"文档上传成功: {doc['id']}")

    # 等待索引
    if wait_for_indexing(doc['id']):
        # 执行RAG查询
        result = rag_query(
            collection_ids=[collection['id']],
            query="VoiceHelper支持哪些语音识别语言？",
            user_id=user_id,
            top_k=5
        )

        print("\n=== RAG检索结果 ===")
        print(f"问题: {result['query']}")
        print(f"答案: {result['answer']}")
        print(f"\n引用来源 ({len(result['citations'])}):")
        for i, cite in enumerate(result['citations'], 1):
            print(f"  [{i}] {cite['title']}")
            print(f"      片段: {cite['snippet'][:100]}...")
            print(f"      相似度: {cite['score']:.3f}")
    else:
        print("文档索引失败，无法执行查询")
```

**关键要点**

1. **文档格式**：支持 PDF、DOCX、TXT、Markdown 等
2. **索引时间**：根据文档大小，可能需要几秒到几分钟
3. **状态轮询**：定期检查文档状态，避免在未索引完成时查询
4. **检索模式**：
   - `vector`：向量检索（语义匹配）
   - `bm25`：关键词检索
   - `hybrid`：混合检索（推荐）
5. **重排序**：启用 `enable_rerank` 提升结果质量

---

## 实战经验

### 经验 1: 上下文管理最佳实践

**问题描述**

长对话场景中，上下文不断增长，导致 Token 超限和响应变慢。

**解决方案**

```python
# 配置上下文压缩策略
conversation_config = {
    "context": {
        "max_tokens": 4000,
        "strategy": "hybrid",  # 混合策略
        "compression": {
            "enabled": True,
            "target_ratio": 0.5,  # 压缩到原来的50%
            "preserve_recent": 5   # 保留最近5条原始消息
        }
    }
}

# 在创建对话时应用配置
conversation = create_conversation(
    user_id="user_123",
    tenant_id="tenant_abc",
    title="长对话测试",
    mode="text",
    config=conversation_config
)
```

**经验总结**

1. **固定窗口**：简单但可能丢失重要上下文
2. **滑动窗口**：保留最近 N 条消息，适合短对话
3. **Token 限制**：根据模型限制动态裁剪
4. **摘要压缩**：对旧消息生成摘要，适合长对话
5. **混合策略**：旧消息摘要+新消息保留，平衡信息损失和性能

**监控指标**

- 平均上下文 Token 数：<= 模型限制的 80%
- 压缩比：0.4-0.6
- 压缩延迟：<= 200ms
- 信息保留率：>= 85%（通过评估集测试）

---

### 经验 2: Agent 工具调用失败处理

**问题描述**

Agent 调用外部工具时，可能因为网络、权限、参数错误等原因失败。

**解决方案**

```python
# 工具执行包装器
class ResilientToolExecutor:
    def __init__(self, tool, max_retries=3, timeout=30):
        self.tool = tool
        self.max_retries = max_retries
        self.timeout = timeout

    async def execute(self, **kwargs):
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # 设置超时
                result = await asyncio.wait_for(
                    self.tool.execute(**kwargs),
                    timeout=self.timeout
                )
                return {
                    "success": True,
                    "result": result,
                    "attempts": attempt + 1
                }

            except asyncio.TimeoutError:
                last_error = f"工具执行超时（{self.timeout}秒）"
                print(f"尝试 {attempt + 1}/{self.max_retries} 失败: {last_error}")
                await asyncio.sleep(2 ** attempt)  # 指数退避

            except ValueError as e:
                # 参数错误不重试
                return {
                    "success": False,
                    "error": f"参数错误: {str(e)}",
                    "attempts": attempt + 1,
                    "suggestion": "请检查工具参数格式"
                }

            except Exception as e:
                last_error = str(e)
                print(f"尝试 {attempt + 1}/{self.max_retries} 失败: {last_error}")
                await asyncio.sleep(2 ** attempt)

        # 所有重试失败
        return {
            "success": False,
            "error": last_error,
            "attempts": self.max_retries,
            "suggestion": "工具暂时不可用，请稍后重试或使用其他工具"
        }

# 在Agent Executor中使用
async def _execute_tool_with_resilience(self, tool_name, tool_input):
    tool = self.tool_registry.get_tool(tool_name)
    if not tool:
        return f"错误: 工具 '{tool_name}' 不存在"

    executor = ResilientToolExecutor(tool, max_retries=3, timeout=30)
    result = await executor.execute(**tool_input)

    if result["success"]:
        return result["result"]
    else:
        return f"工具执行失败: {result['error']}。建议: {result.get('suggestion', '无')}"
```

**经验总结**

1. **重试策略**：指数退避（1s、2s、4s...）
2. **超时控制**：设置合理的超时时间
3. **错误分类**：
   - 参数错误：不重试，返回修正建议
   - 临时错误：重试
   - 永久错误：不重试，记录日志
4. **降级方案**：工具失败时，返回友好的错误信息，让 Agent 选择其他工具
5. **监控告警**：工具失败率 > 5% 触发告警

---

### 经验 3: 流式响应断线重连

**问题描述**

网络不稳定时，流式响应可能中断，导致用户体验差。

**解决方案**

```python
import requests
import json
import time

class StreamChatClient:
    def __init__(self, base_url, token, max_retries=3):
        self.base_url = base_url
        self.token = token
        self.max_retries = max_retries

    def stream_chat_with_retry(self, conversation_id, message):
        """带重连的流式对话"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "stream": True
        }

        retry_count = 0
        last_position = 0  # 记录已接收的字符位置
        full_response = ""

        while retry_count < self.max_retries:
            try:
                # 如果是重连，添加 resume_from 参数
                if last_position > 0:
                    payload["resume_from"] = last_position
                    print(f"\n[重连] 从位置 {last_position} 继续...")

                response = requests.post(
                    f"{self.base_url}/api/v1/ai/chat/stream",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=(10, 60)  # 连接超时10s，读取超时60s
                )

                response.raise_for_status()

                # 接收流式数据
                for line in response.iter_lines():
                    if not line or not line.startswith(b"data: "):
                        continue

                    data_str = line[6:].decode('utf-8')

                    if data_str.strip() == "[DONE]":
                        print("\n[完成]")
                        return full_response

                    try:
                        data = json.loads(data_str)

                        if data.get("type") == "delta":
                            delta = data.get("delta", "")
                            print(delta, end="", flush=True)
                            full_response += delta
                            last_position += len(delta)

                    except json.JSONDecodeError:
                        continue

                # 正常结束
                return full_response

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as e:
                retry_count += 1
                print(f"\n[错误] 连接中断: {str(e)}")

                if retry_count < self.max_retries:
                    wait_time = 2 ** retry_count
                    print(f"[重试] {wait_time}秒后重连...")
                    time.sleep(wait_time)
                else:
                    print(f"[失败] 已达到最大重试次数")
                    raise

        return full_response

# 使用示例
client = StreamChatClient(
    base_url="http://api.voiceassistant.com",
    token="your_token",
    max_retries=3
)

response = client.stream_chat_with_retry(
    conversation_id="conv_123",
    message="请详细介绍一下微服务架构"
)

print(f"\n\n完整回复: {len(response)} 字符")
```

**经验总结**

1. **断点续传**：服务端支持 `resume_from` 参数，客户端记录接收位置
2. **超时设置**：连接超时和读取超时分别设置
3. **重连策略**：指数退避，最多 3 次
4. **状态保存**：缓存已接收内容，避免重复显示
5. **用户提示**：清晰提示重连状态，提升用户体验

**服务端支持**（伪代码）

```python
@app.post("/api/v1/ai/chat/stream")
async def stream_chat(request: StreamChatRequest):
    resume_from = request.resume_from or 0

    # 如果是断线重连，从缓存加载之前的响应
    if resume_from > 0:
        cached_response = await redis.get(f"stream:cache:{request.conversation_id}")
        if cached_response and len(cached_response) > resume_from:
            # 跳过已发送的部分，继续发送剩余内容
            pass

    # 流式生成并缓存
    async for chunk in generate_stream():
        # 缓存到Redis（TTL 5分钟）
        await redis.append(f"stream:cache:{request.conversation_id}", chunk)
        yield chunk
```

---

### 经验 4: 多租户隔离与配额管理

**问题描述**

不同租户之间需要数据隔离和资源配额控制。

**解决方案**

```python
# 租户配额检查中间件
from functools import wraps
from flask import request, jsonify

def check_tenant_quota(resource_type):
    """租户配额检查装饰器"""
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            tenant_id = request.headers.get('X-Tenant-ID')
            if not tenant_id:
                return jsonify({"error": "Missing tenant_id"}), 400

            # 获取租户配额
            tenant = await get_tenant(tenant_id)
            if not tenant:
                return jsonify({"error": "Invalid tenant"}), 403

            # 检查配额
            quota = tenant['quota']
            usage = tenant['usage']

            if resource_type == 'messages':
                if usage['message_count'] >= quota['max_messages_per_day']:
                    return jsonify({
                        "error": "Daily message quota exceeded",
                        "quota": quota['max_messages_per_day'],
                        "used": usage['message_count']
                    }), 429

            elif resource_type == 'tokens':
                if usage['tokens_this_month'] >= quota['max_tokens_per_month']:
                    return jsonify({
                        "error": "Monthly token quota exceeded",
                        "quota": quota['max_tokens_per_month'],
                        "used": usage['tokens_this_month']
                    }), 429

            elif resource_type == 'documents':
                if usage['document_count'] >= quota['max_documents']:
                    return jsonify({
                        "error": "Document quota exceeded",
                        "quota": quota['max_documents'],
                        "used": usage['document_count']
                    }), 429

            # 执行实际业务逻辑
            result = await f(*args, **kwargs)

            # 更新使用量
            await update_tenant_usage(tenant_id, resource_type, result)

            return result

        return decorated_function
    return decorator

# 应用到API端点
@app.post("/api/v1/conversations/{id}/messages")
@check_tenant_quota('messages')
async def send_message(id: str):
    # 业务逻辑
    pass

# 数据隔离查询示例
async def list_conversations(user_id: str, tenant_id: str):
    """列出对话（强制租户隔离）"""
    # WHERE 条件必须包含 tenant_id
    query = """
    SELECT * FROM conversations
    WHERE user_id = $1 AND tenant_id = $2
    ORDER BY created_at DESC
    """
    return await db.fetch(query, user_id, tenant_id)
```

**经验总结**

1. **强制隔离**：所有数据查询必须包含 `tenant_id` 过滤
2. **配额维度**：
   - 消息数：每日限制
   - Token 数：每月限制
   - 文档数：总量限制
   - API 调用数：每日限制
   - 存储空间：总量限制
3. **超限处理**：
   - 软限制：警告但允许继续（超出 10%以内）
   - 硬限制：拒绝请求，返回 429
4. **配额重置**：定时任务（Cron）每日/每月重置
5. **监控告警**：配额使用率 > 80% 发送通知

---

## 具体案例

### 案例 1: 智能客服场景

**业务需求**

构建一个智能客服系统，支持产品咨询、订单查询、售后服务。

**技术方案**

```python
# 客服机器人配置
bot_config = {
    "name": "产品客服助手",
    "mode": "rag",  # 基于知识库的RAG模式
    "knowledge_bases": ["product_docs", "faq", "user_manual"],
    "context_window": 10,  # 保留最近10条消息
    "temperature": 0.2,  # 低温度保证回复准确
    "enable_tools": ["order_query", "user_info", "create_ticket"],
    "system_prompt": """
    你是一个专业的产品客服助手。你的职责是:
    1. 解答用户关于产品的问题
    2. 帮助用户查询订单状态
    3. 处理售后服务请求

    回复要求:
    - 友好、专业、耐心
    - 基于知识库内容回答，不编造信息
    - 如果不确定，引导用户联系人工客服
    - 每次回复都引用相关文档来源
    """
}

# 实现客服对话流程
class CustomerServiceBot:
    def __init__(self, config):
        self.config = config
        self.api_client = APIClient()

    async def handle_user_message(self, user_id, tenant_id, message):
        """处理用户消息"""
        # 1. 创建或获取对话
        conversation = await self.get_or_create_conversation(
            user_id, tenant_id
        )

        # 2. 意图识别
        intent = await self.classify_intent(message)

        # 3. 根据意图选择处理策略
        if intent == "order_query":
            # 订单查询：使用Agent模式调用订单查询工具
            response = await self.query_order(conversation['id'], message)

        elif intent == "product_question":
            # 产品咨询：使用RAG模式基于知识库回答
            response = await self.rag_answer(conversation['id'], message)

        elif intent == "complaint":
            # 投诉建议：创建工单并转人工
            response = await self.create_ticket(user_id, message)

        else:
            # 通用对话
            response = await self.chat(conversation['id'], message)

        return response

    async def classify_intent(self, message):
        """意图识别"""
        # 使用LLM进行意图分类
        prompt = f"""
        分类以下用户消息的意图，只返回一个类别:
        - order_query: 订单查询
        - product_question: 产品咨询
        - complaint: 投诉建议
        - general: 通用对话

        用户消息: {message}

        意图类别:
        """

        result = await self.api_client.llm_generate(prompt, max_tokens=10)
        return result.strip().lower()

    async def rag_answer(self, conversation_id, question):
        """RAG问答"""
        response = await self.api_client.rag_query(
            conversation_id=conversation_id,
            query=question,
            knowledge_base_ids=self.config["knowledge_bases"],
            top_k=5,
            enable_rerank=True
        )

        # 格式化回复，包含引用来源
        answer = response['answer']
        citations = response.get('citations', [])

        if citations:
            answer += "\n\n📚 参考资料:"
            for i, cite in enumerate(citations[:3], 1):
                answer += f"\n[{i}] {cite['title']}"

        return answer

    async def query_order(self, conversation_id, message):
        """订单查询"""
        # 使用Agent模式，调用order_query工具
        result = await self.api_client.execute_agent(
            task=f"帮用户查询订单: {message}",
            mode="react",
            tools=["order_query", "user_info"],
            conversation_id=conversation_id
        )

        return result['final_answer']

    async def create_ticket(self, user_id, message):
        """创建工单"""
        # 调用工单系统API
        ticket = await self.api_client.create_ticket(
            user_id=user_id,
            title="用户投诉",
            content=message,
            priority="high"
        )

        return f"""
        非常抱歉给您带来不便。我已为您创建工单 #{ticket['id']}。
        人工客服将在1小时内联系您。

        您也可以拨打客服热线 400-xxx-xxxx 获取即时帮助。
        """

# 使用示例
bot = CustomerServiceBot(bot_config)

async def main():
    # 模拟用户对话
    user_id = "user_123"
    tenant_id = "company_abc"

    # 场景1: 产品咨询
    response1 = await bot.handle_user_message(
        user_id, tenant_id,
        "VoiceHelper支持哪些语音识别语言？"
    )
    print(f"Bot: {response1}")

    # 场景2: 订单查询
    response2 = await bot.handle_user_message(
        user_id, tenant_id,
        "帮我查一下订单 ORD-2024-001 的物流状态"
    )
    print(f"Bot: {response2}")

    # 场景3: 投诉
    response3 = await bot.handle_user_message(
        user_id, tenant_id,
        "产品质量有问题，要求退款"
    )
    print(f"Bot: {response3}")
```

**效果评估**

- **问题解决率**：85%（用户问题通过机器人解决，无需转人工）
- **平均响应时间**：2.3 秒
- **用户满意度**：4.2/5.0
- **人工客服工作量减少**：60%

---

### 案例 2: 文档智能问答系统

**业务需求**

企业内部有大量技术文档，员工需要快速查找信息。

**技术方案**

1. **文档预处理**：解析 PDF/DOCX，语义分块
2. **向量化索引**：使用 BGE-large-zh-v1.5 生成向量
3. **混合检索**：向量检索 + BM25 关键词检索
4. **重排序**：使用 LLM 对 Top-20 结果重排
5. **答案生成**：基于 Top-5 文档生成答案

**代码示例**

```python
# 完整的文档问答pipeline
class DocumentQASystem:
    def __init__(self):
        self.api_client = APIClient()
        self.collection_id = None

    async def initialize(self, documents_dir):
        """初始化：上传文档并建立索引"""
        # 创建知识库
        collection = await self.api_client.create_collection(
            name="技术文档库",
            description="公司内部技术文档"
        )
        self.collection_id = collection['id']

        # 批量上传文档
        import os
        doc_ids = []
        for filename in os.listdir(documents_dir):
            if filename.endswith(('.pdf', '.docx', '.md')):
                file_path = os.path.join(documents_dir, filename)
                doc = await self.api_client.upload_document(
                    collection_id=self.collection_id,
                    file_path=file_path
                )
                doc_ids.append(doc['id'])
                print(f"上传文档: {filename} -> {doc['id']}")

        # 等待所有文档索引完成
        await self.wait_all_documents_ready(doc_ids)

        print(f"初始化完成: {len(doc_ids)} 个文档已索引")

    async def wait_all_documents_ready(self, doc_ids, timeout=600):
        """等待所有文档索引完成"""
        import asyncio

        pending = set(doc_ids)
        start_time = time.time()

        while pending and time.time() - start_time < timeout:
            for doc_id in list(pending):
                doc = await self.api_client.get_document(doc_id)
                if doc['status'] == 'READY':
                    pending.remove(doc_id)
                    print(f"✓ 文档 {doc_id} 索引完成")
                elif doc['status'] == 'FAILED':
                    pending.remove(doc_id)
                    print(f"✗ 文档 {doc_id} 索引失败")

            if pending:
                await asyncio.sleep(5)

        return len(pending) == 0

    async def ask(self, question, top_k=5, enable_rerank=True):
        """问答"""
        result = await self.api_client.rag_query(
            query=question,
            knowledge_base_ids=[self.collection_id],
            top_k=top_k,
            enable_rerank=enable_rerank,
            retrieval_mode="hybrid"
        )

        return {
            "question": question,
            "answer": result['answer'],
            "sources": [
                {
                    "document": cite['document_name'],
                    "page": cite.get('page', 'N/A'),
                    "score": cite['score']
                }
                for cite in result.get('citations', [])
            ],
            "confidence": result.get('confidence', 0.0)
        }

    async def batch_ask(self, questions):
        """批量问答"""
        import asyncio
        tasks = [self.ask(q) for q in questions]
        results = await asyncio.gather(*tasks)
        return results

# 使用示例
async def main():
    qa_system = DocumentQASystem()

    # 初始化（仅首次运行）
    await qa_system.initialize("./docs/technical/")

    # 单个问题
    result = await qa_system.ask("如何部署Kubernetes集群？")
    print(f"问题: {result['question']}")
    print(f"答案: {result['answer']}")
    print(f"置信度: {result['confidence']:.2f}")
    print(f"来源文档: {len(result['sources'])} 个")
    for src in result['sources']:
        print(f"  - {src['document']} (相似度: {src['score']:.3f})")

    # 批量问题
    questions = [
        "如何配置Istio服务网格？",
        "PostgreSQL主从复制如何设置？",
        "Prometheus监控指标如何采集？"
    ]
    results = await qa_system.batch_ask(questions)

    for r in results:
        print(f"\nQ: {r['question']}")
        print(f"A: {r['answer'][:200]}...")
```

**效果评估**

- **检索准确率**：91%（Top-5 包含正确答案）
- **答案准确率**：87%（答案正确且完整）
- **平均响应时间**：1.8 秒
- **员工查找文档效率提升**：3 倍

---

### 案例 3: 多轮对话任务执行

**业务需求**

用户通过自然语言交互，完成复杂的多步骤任务。

**示例任务**

"帮我分析最近一周的销售数据，找出销量前 10 的产品，然后生成一份分析报告发送给我的邮箱"

**技术方案**

使用 Plan-Execute 模式，Agent 自动分解任务并执行。

**代码示例**

```python
# 注册自定义工具
from app.tools.tool_registry import ToolRegistry

registry = ToolRegistry()

# 工具1: 查询销售数据
async def query_sales_data(start_date: str, end_date: str) -> dict:
    """查询销售数据"""
    # 调用数据库或数据仓库API
    data = await db.query(f"""
        SELECT product_id, product_name, SUM(quantity) as total_sales
        FROM sales
        WHERE sale_date BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY product_id, product_name
        ORDER BY total_sales DESC
        LIMIT 10
    """)
    return {"data": data, "count": len(data)}

registry.register_tool(
    name="query_sales_data",
    description="查询指定时间范围的销售数据",
    function=query_sales_data,
    parameters={
        "start_date": {
            "type": "string",
            "description": "开始日期 (YYYY-MM-DD)",
            "required": True
        },
        "end_date": {
            "type": "string",
            "description": "结束日期 (YYYY-MM-DD)",
            "required": True
        }
    }
)

# 工具2: 生成报告
async def generate_report(data: dict, template: str = "sales") -> str:
    """生成分析报告"""
    # 使用LLM生成报告
    prompt = f"""
    基于以下销售数据生成一份专业的分析报告:

    {json.dumps(data, ensure_ascii=False, indent=2)}

    报告应包括:
    1. 数据概要
    2. Top 10产品分析
    3. 趋势insights
    4. 建议
    """

    report = await llm_client.generate(prompt, max_tokens=2000)
    return report

registry.register_tool(
    name="generate_report",
    description="基于数据生成分析报告",
    function=generate_report,
    parameters={
        "data": {
            "type": "object",
            "description": "要分析的数据",
            "required": True
        },
        "template": {
            "type": "string",
            "description": "报告模板类型",
            "required": False
        }
    }
)

# 工具3: 发送邮件
async def send_email(to: str, subject: str, body: str) -> dict:
    """发送邮件"""
    # 调用邮件服务
    result = await email_service.send(
        to=to,
        subject=subject,
        body=body,
        content_type="text/html"
    )
    return {"status": "sent", "message_id": result.message_id}

registry.register_tool(
    name="send_email",
    description="发送邮件",
    function=send_email,
    parameters={
        "to": {
            "type": "string",
            "description": "收件人邮箱",
            "required": True
        },
        "subject": {
            "type": "string",
            "description": "邮件主题",
            "required": True
        },
        "body": {
            "type": "string",
            "description": "邮件正文",
            "required": True
        }
    }
)

# 执行复杂任务
async def execute_complex_task():
    from datetime import datetime, timedelta

    # 用户任务
    task = """
    帮我分析最近一周的销售数据，找出销量前10的产品，
    然后生成一份分析报告发送给 manager@company.com
    """

    # 使用Plan-Execute模式
    result = await agent_engine.execute(
        task=task,
        mode="plan_execute",
        max_steps=20,
        tools=["query_sales_data", "generate_report", "send_email"]
    )

    print("=" * 60)
    print("任务执行完成!")
    print("=" * 60)
    print(f"状态: {result['status']}")
    print(f"步骤数: {result['step_count']}")
    print(f"执行时间: {result['execution_time']:.2f}s")
    print("\n执行计划:")
    for i, step in enumerate(result['steps'], 1):
        print(f"\n步骤 {i}:")
        print(f"  动作: {step.get('action', 'N/A')}")
        if 'observation' in step:
            print(f"  结果: {step['observation'][:100]}...")
    print("\n最终答案:")
    print(result['final_answer'])
    print("=" * 60)

# 运行
if __name__ == "__main__":
    import asyncio
    asyncio.run(execute_complex_task())
```

**执行过程**

1. **Plan 阶段**：Agent 分解任务为 3 个子任务

   - 查询最近 7 天销售数据
   - 生成分析报告
   - 发送邮件

2. **Execute 阶段**：逐个执行子任务

   - 步骤 1：调用`query_sales_data`工具，获取销售数据
   - 步骤 2：调用`generate_report`工具，生成报告
   - 步骤 3：调用`send_email`工具，发送邮件

3. **结果**：任务成功完成，报告已发送
