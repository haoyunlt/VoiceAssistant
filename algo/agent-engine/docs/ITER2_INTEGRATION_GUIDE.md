# Agent Engine Iteration 2 集成指南

> **版本**: v2.0
> **日期**: 2025-11-29
> **适用于**: Agent Engine Iteration 2

---

## 📖 概览

本指南介绍如何使用 Agent Engine Iteration 2 的三大核心功能：

1. **Self-RAG** - 自检索、自评估、自修正的高质量问答系统
2. **智能记忆管理** - 记忆压缩、智能遗忘、混合检索
3. **Multi-Agent 协作** - 多智能体协同工作、任务分解、冲突解决

---

## 🚀 快速开始

### 1. 启动服务

```bash
# 进入 agent-engine 目录
cd /path/to/agent-engine

# 激活虚拟环境
source venv/bin/activate

# 启动服务
python main.py
```

服务将在 `http://localhost:8003` 启动。

### 2. 查看 API 文档

访问 `http://localhost:8003/docs` 查看完整的 API 文档（Swagger UI）。

### 3. 运行演示

```bash
# 运行集成演示
python examples/iter2_integration_demo.py
```

---

## 🎯 功能使用指南

### Self-RAG 使用

#### API 端点

**POST** `/self-rag/query`

#### 请求示例

```bash
curl -X POST "http://localhost:8003/self-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "什么是RAG，它如何帮助LLM减少幻觉？",
    "mode": "adaptive",
    "enable_citations": true,
    "max_refinements": 2
  }'
```

#### 响应示例

```json
{
  "query": "什么是RAG，它如何帮助LLM减少幻觉？",
  "answer": "RAG (Retrieval-Augmented Generation) 是一种结合检索和生成的技术...",
  "confidence": 0.92,
  "retrieval_strategy": "hybrid",
  "refinement_count": 1,
  "hallucination_level": "low",
  "is_grounded": true,
  "citations": [
    {
      "source": "doc_001",
      "text": "RAG技术通过..."
    },
    {
      "source": "doc_042",
      "text": "减少幻觉的关键..."
    }
  ],
  "metadata": {}
}
```

#### Self-RAG 模式

- **adaptive** (默认): 根据查询复杂度自动选择策略
- **standard**: 标准 Self-RAG 流程
- **strict**: 严格模式，多轮验证
- **fast**: 快速模式，减少修正次数

#### Python SDK 示例

```python
import asyncio
from app.core.self_rag.self_rag_service import SelfRAGService
from app.core.self_rag.adaptive_retriever import AdaptiveRetriever
from app.core.self_rag.critique import RetrievalCritic
from app.core.self_rag.hallucination_detector import HallucinationDetector

async def main():
    # 初始化组件
    retriever = AdaptiveRetriever(knowledge_base=kb, cache=cache)
    critic = RetrievalCritic(llm_client=llm)
    detector = HallucinationDetector(llm_client=llm)

    service = SelfRAGService(
        llm_client=llm,
        retriever=retriever,
        critic=critic,
        detector=detector
    )

    # 执行查询
    result = await service.process_query(
        query="什么是RAG？",
        context={}
    )

    print(f"答案: {result['final_answer']}")
    print(f"置信度: {result['retrieval_assessment'].confidence}")

asyncio.run(main())
```

---

### 智能记忆管理使用

#### API 端点

- **POST** `/smart-memory/add` - 添加记忆
- **POST** `/smart-memory/retrieve` - 检索记忆
- **POST** `/smart-memory/compress` - 压缩记忆
- **POST** `/smart-memory/maintain` - 维护记忆
- **GET** `/smart-memory/stats` - 获取统计

#### 添加记忆

```bash
curl -X POST "http://localhost:8003/smart-memory/add" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "content": "用户喜欢技术文档，关注AI和RAG",
    "tier": "long_term",
    "importance": 0.9,
    "metadata": {
      "category": "user_preference"
    }
  }'
```

响应：
```json
{
  "memory_id": "mem_12345",
  "tier": "long_term",
  "importance": 0.9,
  "message": "Memory added successfully"
}
```

#### 检索记忆

```bash
curl -X POST "http://localhost:8003/smart-memory/retrieve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "用户对RAG感兴趣吗？",
    "top_k": 5,
    "tier_filter": null,
    "min_importance": 0.5
  }'
```

#### 记忆层级

- **working**: 工作记忆（当前任务相关）
- **short_term**: 短期记忆（最近对话）
- **long_term**: 长期记忆（持久保存）

#### Python SDK 示例

```python
from app.core.memory.smart_memory_manager import SmartMemoryManager, MemoryTier

async def manage_memory():
    manager = SmartMemoryManager(
        llm_client=llm,
        vector_store_client=vector_store,
        config=config
    )

    # 添加记忆
    mem_id = await manager.add_memory(
        content="用户询问了RAG部署问题",
        tier=MemoryTier.SHORT_TERM,
        importance=0.7
    )

    # 检索记忆
    memories = await manager.retrieve(
        query="RAG相关讨论",
        top_k=5
    )

    # 自动维护（压缩、遗忘、提升）
    await manager.auto_maintain()

    # 获取统计
    stats = manager.get_stats()
    print(f"总记忆数: {stats['total_memories']}")
```

---

### Multi-Agent 协作使用

#### API 端点

- **POST** `/multi-agent/collaborate` - 执行协作任务
- **POST** `/multi-agent/agents/register` - 注册 Agent
- **GET** `/multi-agent/agents` - 列出所有 Agents
- **DELETE** `/multi-agent/agents/{agent_id}` - 注销 Agent
- **GET** `/multi-agent/stats` - 获取统计

#### 注册 Agent

```bash
curl -X POST "http://localhost:8003/multi-agent/agents/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "agent_id": "researcher_01",
    "role": "researcher",
    "tools": ["search_tool", "knowledge_tool"]
  }'
```

#### 执行协作任务

```bash
curl -X POST "http://localhost:8003/multi-agent/collaborate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "task": "分析人工智能在医疗领域的应用现状和未来趋势",
    "mode": "parallel",
    "agent_ids": ["researcher_01", "planner_01", "executor_01"],
    "priority": 8
  }'
```

响应：
```json
{
  "task": "分析人工智能在医疗领域的应用现状和未来趋势",
  "mode": "parallel",
  "agents_involved": ["researcher_01", "planner_01", "executor_01"],
  "final_result": "综合分析报告...",
  "quality_score": 0.88,
  "completion_time": 5.2,
  "status": "completed",
  "metadata": {}
}
```

#### 协作模式

- **sequential**: 串行执行（按顺序）
- **parallel**: 并行执行（同时进行）
- **debate**: 辩论模式（多轮讨论达成共识）
- **voting**: 投票模式（多数决定）
- **hierarchical**: 分层模式（协调者分配任务给工作者）

#### Agent 角色

- **coordinator**: 协调者（任务分解、结果合并）
- **researcher**: 研究员（信息收集、调研）
- **planner**: 规划者（计划制定、架构设计）
- **executor**: 执行者（具体实现、操作执行）
- **reviewer**: 审查者（质量检查、结果验证）

#### Python SDK 示例

```python
from app.core.multi_agent.enhanced_coordinator import EnhancedMultiAgentCoordinator
from app.core.multi_agent.coordinator import Agent, AgentRole

async def multi_agent_demo():
    coordinator = EnhancedMultiAgentCoordinator(
        llm_client=llm,
        tool_registry=tool_registry,
        config=config
    )

    # 注册 Agents
    agents = [
        Agent("researcher_01", AgentRole.RESEARCHER, llm),
        Agent("planner_01", AgentRole.PLANNER, llm),
        Agent("executor_01", AgentRole.EXECUTOR, llm),
    ]

    for agent in agents:
        await coordinator.register_agent(agent)

    # 启动协调器
    await coordinator.start()

    # 执行协作任务
    result = await coordinator.collaborate(
        task="构建AI客服系统",
        mode="hierarchical",
        priority=10
    )

    print(f"结果: {result['final_output']}")
    print(f"质量评分: {result['quality_score']}")

    # 停止协调器
    await coordinator.stop()
```

---

## 🔗 集成场景示例

### 场景：智能客服问答系统

完整流程展示如何结合三大功能：

```python
import asyncio
from app.core.self_rag.self_rag_service import SelfRAGService
from app.core.memory.smart_memory_manager import SmartMemoryManager
from app.core.multi_agent.enhanced_coordinator import EnhancedMultiAgentCoordinator

async def intelligent_customer_service(user_query: str, user_id: str):
    """智能客服完整流程"""

    # 1. 从记忆中获取用户上下文
    context = await memory_manager.get_context_for_agent(
        conversation_id=user_id,
        current_query=user_query,
        max_tokens=1000,
        retrieval_mode="hybrid"
    )

    # 2. 使用 Self-RAG 检索和生成答案
    rag_result = await self_rag_service.process_query(
        query=user_query,
        context=context
    )

    # 3. 如果问题复杂，调用 Multi-Agent 协作
    if rag_result["confidence"] < 0.8:
        ma_result = await multi_agent_coordinator.collaborate(
            task=f"深入解答：{user_query}",
            mode="parallel",
            agent_ids=["researcher_01", "planner_01", "executor_01"],
            priority=8
        )

        final_answer = ma_result["final_output"]
        quality_score = ma_result["quality_score"]
    else:
        final_answer = rag_result["final_answer"]
        quality_score = rag_result["confidence"]

    # 4. 更新记忆
    await memory_manager.add_memory(
        content=f"用户询问: {user_query}",
        tier="short_term",
        importance=0.7,
        metadata={"timestamp": datetime.now().isoformat()}
    )

    await memory_manager.add_memory(
        content=f"系统回答: {final_answer[:100]}...",
        tier="short_term",
        importance=0.6
    )

    # 5. 自动维护记忆
    await memory_manager.auto_maintain()

    return {
        "answer": final_answer,
        "quality_score": quality_score,
        "sources": rag_result.get("citations", []),
        "context_used": context["has_summary"],
    }

# 运行
result = await intelligent_customer_service(
    user_query="如何在生产环境中部署高可用的RAG系统？",
    user_id="user_12345"
)

print(f"答案: {result['answer']}")
print(f"质量评分: {result['quality_score']}")
```

---

## 📊 监控与指标

### 获取 Self-RAG 统计

```bash
curl "http://localhost:8003/self-rag/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 获取记忆统计

```bash
curl "http://localhost:8003/smart-memory/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 获取 Multi-Agent 统计

```bash
curl "http://localhost:8003/multi-agent/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Prometheus 指标

访问 `http://localhost:8003/metrics` 获取 Prometheus 格式的指标。

关键指标：
- `self_rag_queries_total` - Self-RAG 查询总数
- `self_rag_refinements_total` - 修正次数
- `memory_operations_total` - 记忆操作总数
- `multi_agent_tasks_total` - Multi-Agent 任务总数
- `collaboration_quality_score` - 协作质量评分

---

## 🔧 配置

### 环境变量

在 `.env` 文件中配置：

```bash
# Self-RAG 配置
SELF_RAG_ENABLED=true
SELF_RAG_MODE=adaptive
SELF_RAG_MAX_REFINEMENTS=2
SELF_RAG_HALLUCINATION_THRESHOLD=0.3
SELF_RAG_ENABLE_CITATIONS=true

# 智能记忆配置
SMART_MEMORY_ENABLED=true
MEMORY_COMPRESSION_ENABLED=true
MEMORY_COMPRESSION_THRESHOLD=20
MEMORY_FORGETTING_STRATEGY=hybrid
MEMORY_IMPORTANCE_THRESHOLD=0.3

# Multi-Agent 配置
MULTI_AGENT_ENABLED=false  # 默认关闭，按需启用
MULTI_AGENT_DEFAULT_MODE=parallel
MULTI_AGENT_MAX_CONCURRENT=5
MULTI_AGENT_QUALITY_CHECK=true
```

---

## 🧪 测试

### 运行集成测试

```bash
# 运行所有 Iteration 2 测试
pytest tests/test_iter2_integration.py -v

# 运行特定测试类
pytest tests/test_iter2_integration.py::TestSelfRAGIntegration -v

# 运行特定测试方法
pytest tests/test_iter2_integration.py::TestSelfRAGIntegration::test_self_rag_query_flow -v
```

---

## 🚨 故障排除

### Self-RAG 置信度低

**问题**: Self-RAG 返回的置信度持续偏低。

**解决方案**:
1. 检查知识库数据质量
2. 调整检索策略（尝试 `hybrid` 模式）
3. 增加 `max_refinements` 参数
4. 检查 LLM 模型性能

### 记忆无法压缩

**问题**: 记忆压缩失败或效果不佳。

**解决方案**:
1. 确保 LLM 服务可用
2. 检查记忆数量是否达到压缩阈值
3. 调整 `memory_compression_threshold` 参数
4. 查看日志获取详细错误信息

### Multi-Agent 协作超时

**问题**: Multi-Agent 任务执行超时。

**解决方案**:
1. 减少并发 Agents 数量
2. 简化任务描述
3. 增加超时时间配置
4. 检查 Agent 工具可用性

---

## 📞 支持与反馈

- **文档**: `/docs/`
- **Issue Tracker**: GitHub Issues
- **Slack**: `#agent-engine-dev`

---

**版本**: Iteration 2 - v2.0
**更新日期**: 2025-11-29
