# RAG Engine v2.0 使用指南

> **Iter 2 & 3 功能：Graph RAG + Query Decomposition + Self-RAG + Context Compression**

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/rag-engine

# 基础依赖（必需）
pip install -r requirements.txt

# 可选：Neo4j 驱动（企业级图谱）
pip install neo4j==5.15.0

# 可选：Transformers（NLI 幻觉检测）
pip install transformers==4.36.0

# 可选：LLMLingua（高质量压缩）
pip install llmlingua==0.2.0
```

### 2. 启动 Redis（缓存）

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. 可选：启动 Neo4j（图谱）

```bash
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15-community
```

### 4. 运行服务

```bash
# 开发模式
make run

# 或
python main.py
```

---

## 📖 基础用法

### 场景 1: 简单问答（使用所有优化）

```python
import asyncio
from app.services.ultimate_rag_service import get_ultimate_rag_service

async def main():
    # 初始化服务（启用所有功能）
    service = get_ultimate_rag_service(
        retrieval_client=retrieval_client,
        llm_client=llm_client,
        enable_hybrid=True,          # Iter 1: 混合检索
        enable_rerank=True,          # Iter 1: 重排
        enable_cache=True,           # Iter 1: 语义缓存
        enable_graph=True,           # Iter 2: 图谱检索
        enable_decomposition=True,   # Iter 2: 查询分解
        enable_self_rag=True,        # Iter 3: 自我纠错
        enable_compression=True,     # Iter 3: 上下文压缩
        compression_ratio=0.5,
    )

    # 查询
    result = await service.query(
        query="什么是RAG？它如何工作？",
        tenant_id="user123",
        top_k=5,
        temperature=0.7,
    )

    # 打印结果
    print("答案:", result["answer"])
    print("使用的策略:", result["strategy"])
    print("启用的功能:", result["features_used"])
    print("Self-RAG 信息:", result["self_rag"])
    print("压缩信息:", result["compression"])

asyncio.run(main())
```

### 场景 2: 复杂多跳推理（强调图谱）

```python
result = await service.query(
    query="张三认识李四，李四认识王五，那么张三和王五之间是什么关系？",
    tenant_id="user123",
    top_k=5,
    use_graph=True,           # 启用图谱检索
    use_decomposition=False,  # 不需要分解
    use_self_rag=True,        # 启用自我纠错
    use_compression=False,    # 不压缩（保留完整信息）
)

# 结果会包含图谱路径
print("检索策略:", result["strategy"])  # graph_enhanced
if "entities" in result:
    print("识别的实体:", result["entities"])
if "graph_results_count" in result:
    print("图谱结果数:", result["graph_results_count"])
```

### 场景 3: 复杂组合查询（使用查询分解）

```python
result = await service.query(
    query="对比Python和Java的性能差异，并说明它们各自的优势和劣势",
    tenant_id="user123",
    top_k=5,
    use_graph=False,
    use_decomposition=True,  # 启用查询分解
    use_self_rag=True,
    use_compression=True,
)

# 结果会包含子查询信息
if result.get("strategy") == "query_decomposition":
    print("子查询:", result["sub_queries"])
    print("子答案:", result["sub_answers"])
```

### 场景 4: 长上下文优化（强调压缩）

```python
result = await service.query(
    query="总结这篇论文的核心观点",
    tenant_id="user123",
    top_k=10,  # 检索更多文档
    use_graph=False,
    use_decomposition=False,
    use_self_rag=False,
    use_compression=True,     # 启用压缩
    compression_ratio=0.3,    # 高压缩率（70% Token 节省）
)

# 查看压缩效果
print("Token 节省:", result["compression"]["tokens_saved"])
print("压缩率:", result["compression"]["ratio"])
```

### 场景 5: 高质量回答（强调 Self-RAG）

```python
result = await service.query(
    query="解释量子力学的不确定性原理",
    tenant_id="user123",
    top_k=5,
    use_graph=False,
    use_decomposition=False,
    use_self_rag=True,       # 启用自我纠错
    use_compression=False,
    temperature=0.3,          # 低温度，更精确
)

# 查看 Self-RAG 结果
print("是否有幻觉:", result["self_rag"]["has_hallucination"])
print("置信度:", result["self_rag"]["confidence"])
print("修正次数:", result["self_rag"]["attempts"])
```

---

## 🔧 高级配置

### 1. 自定义图谱后端

#### 使用 NetworkX（默认）

```python
service = get_ultimate_rag_service(
    retrieval_client=retrieval_client,
    llm_client=llm_client,
    enable_graph=True,
    graph_backend="networkx",  # 轻量级，适合开发
)
```

#### 使用 Neo4j（生产推荐）

```python
service = get_ultimate_rag_service(
    retrieval_client=retrieval_client,
    llm_client=llm_client,
    enable_graph=True,
    graph_backend="neo4j",
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
)
```

### 2. 自定义压缩策略

#### 使用规则压缩（默认）

```python
service = get_ultimate_rag_service(
    retrieval_client=retrieval_client,
    llm_client=llm_client,
    enable_compression=True,
    use_llmlingua=False,  # 使用规则方法
    compression_ratio=0.5,
)
```

#### 使用 LLMLingua（高质量）

```python
service = get_ultimate_rag_service(
    retrieval_client=retrieval_client,
    llm_client=llm_client,
    enable_compression=True,
    use_llmlingua=True,  # 需要安装 llmlingua
    compression_ratio=0.5,
)
```

### 3. 调整 Self-RAG 行为

```python
from app.self_rag.hallucination_detector import HallucinationDetector
from app.self_rag.self_rag_service import SelfRAGService

# 自定义 Self-RAG 服务
detector = HallucinationDetector(
    llm_client=llm_client,
    use_nli=True,  # 启用 NLI 模型（需要 transformers）
)

self_rag_service = SelfRAGService(
    llm_client=llm_client,
    hallucination_detector=detector,
    max_refinement_attempts=3,  # 增加修正次数
    hallucination_threshold=0.8,  # 提高检测阈值
)
```

---

## 📊 监控与调试

### 查看服务状态

```python
status = await service.get_service_status()

print("启用的功能:")
print("- Iter 1:", status["iter1_features"])
print("- Iter 2:", status["iter2_features"])
print("- Iter 3:", status["iter3_features"])

if "cache_stats" in status:
    print("\n缓存统计:")
    print(status["cache_stats"])

if "graph_stats" in status:
    print("\n图谱统计:")
    print(status["graph_stats"])
```

### 查看 Prometheus 指标

```bash
# 访问指标端点
curl http://localhost:8006/metrics | grep rag_

# 示例指标
# rag_query_total{mode="ultimate",status="success",tenant_id="user123"} 42
# rag_query_latency_seconds{mode="ultimate",tenant_id="user123"} 2.1
# rag_cache_hit_ratio 0.65
# rag_graph_query_total 15
# rag_hallucination_detected_total 2
# rag_tokens_saved_total 1250
```

### 日志级别

```python
import logging

# 调整日志级别
logging.getLogger("app.graph").setLevel(logging.DEBUG)
logging.getLogger("app.self_rag").setLevel(logging.DEBUG)
logging.getLogger("app.compression").setLevel(logging.DEBUG)
```

---

## 🎯 性能优化技巧

### 1. 缓存预热

```python
# 预加载常见查询到缓存
common_queries = [
    "什么是RAG？",
    "如何使用RAG？",
    "RAG有什么优势？",
]

for query in common_queries:
    await service.query(query, tenant_id="warmup")
```

### 2. 图谱预构建

```python
from app.graph.graph_store import get_graph_store
from app.graph.entity_extractor import EntityExtractor

# 离线构建图谱
graph_store = get_graph_store(backend="networkx")
extractor = EntityExtractor(llm_client)

# 批量处理文档
for doc in documents:
    entities, relations = await extractor.extract_entities_and_relations(
        text=doc["content"],
        use_llm=True
    )

    for entity in entities:
        graph_store.add_node(
            node_id=entity["name"],
            node_type=entity["type"],
            properties={"source": doc["id"]}
        )

    for rel in relations:
        graph_store.add_edge(
            source_id=rel["source"],
            target_id=rel["target"],
            relation=rel["relation"]
        )

# 保存到文件
graph_store.save_to_file("knowledge_graph.json")

# 服务启动时加载
graph_store.load_from_file("knowledge_graph.json")
```

### 3. 并行查询

```python
import asyncio

# 批量查询
queries = [
    "查询1",
    "查询2",
    "查询3",
]

results = await asyncio.gather(*[
    service.query(q, tenant_id="batch") for q in queries
])
```

---

## 🧪 测试示例

### 单元测试

```python
# tests/test_graph_rag.py
import pytest
from app.graph.graph_store import get_graph_store

@pytest.mark.asyncio
async def test_graph_store():
    store = get_graph_store(backend="networkx")

    # 添加节点
    store.add_node("A", "Entity", {"name": "实体A"})
    store.add_node("B", "Entity", {"name": "实体B"})

    # 添加边
    store.add_edge("A", "B", "related_to")

    # 查询
    neighbors = store.get_neighbors("A", max_hops=1)
    assert len(neighbors) == 1
    assert neighbors[0]["id"] == "B"

@pytest.mark.asyncio
async def test_self_rag():
    from app.self_rag.self_rag_service import SelfRAGService
    from app.self_rag.hallucination_detector import HallucinationDetector

    detector = HallucinationDetector(llm_client)
    service = SelfRAGService(llm_client, detector)

    result = await service.generate_with_self_check(
        query="测试查询",
        context="测试上下文",
        temperature=0.7
    )

    assert "answer" in result
    assert "has_hallucination" in result
    assert result["attempts"] >= 1
```

### 集成测试

```python
# tests/test_integration.py
@pytest.mark.asyncio
async def test_ultimate_rag_e2e():
    service = get_ultimate_rag_service(
        retrieval_client=mock_retrieval_client,
        llm_client=mock_llm_client,
        enable_hybrid=True,
        enable_graph=True,
        enable_self_rag=True,
    )

    result = await service.query(
        query="测试复杂查询",
        tenant_id="test",
        use_graph=True,
        use_self_rag=True,
    )

    assert result["answer"]
    assert result["strategy"] in ["graph_enhanced", "query_decomposition", "base"]
    assert "self_rag" in result
```

---

## 🐛 故障排查

### 问题 1: 图谱检索无结果

**症状**: `graph_results_count: 0`

**可能原因**:
1. 图谱未构建或为空
2. 实体抽取失败
3. 图谱后端连接失败

**解决方案**:
```python
# 检查图谱状态
graph_store = service.advanced_rag.graph_store
stats = graph_store.get_stats()
print(f"图谱节点数: {stats['num_nodes']}")
print(f"图谱边数: {stats['num_edges']}")

# 手动测试实体抽取
from app.graph.entity_extractor import EntityExtractor
extractor = EntityExtractor(llm_client)
entities, relations = await extractor.extract_entities_and_relations("测试文本")
print(f"识别的实体: {entities}")
```

### 问题 2: Self-RAG 总是报幻觉

**症状**: `has_hallucination: true` (置信度高)

**可能原因**:
1. 上下文质量差
2. 检测阈值过低
3. LLM 生成质量问题

**解决方案**:
```python
# 1. 提高检测阈值
service = get_ultimate_rag_service(
    ...,
    enable_self_rag=True,
    # 自定义 Self-RAG
)

# 2. 检查上下文
print("检索到的文档数:", len(result["documents"]))
print("文档内容:", [d["content"][:100] for d in result["documents"]])

# 3. 查看检测详情
print("检测结果:", result["self_rag"])
print("检测历史:", result.get("detection_history"))
```

### 问题 3: 压缩后准确率下降

**症状**: 启用压缩后答案质量变差

**可能原因**:
1. 压缩率过高
2. 关键信息被压缩

**解决方案**:
```python
# 1. 降低压缩率
result = await service.query(
    query=query,
    use_compression=True,
    compression_ratio=0.6,  # 从 0.5 提高到 0.6
)

# 2. 对比压缩前后
compressor = service.compressor
compression_result = compressor.compress(
    context="原始上下文",
    query=query,
    compression_ratio=0.5,
    preserve_entities=True,  # 保留实体
    preserve_numbers=True,   # 保留数字
)

print("原始长度:", compression_result["original_length"])
print("压缩后长度:", compression_result["compressed_length"])
print("压缩内容:", compression_result["compressed_context"])
```

### 问题 4: 查询分解效果不好

**症状**: 子查询不合理或答案合并失败

**可能原因**:
1. 查询不够复杂，不需要分解
2. LLM Prompt 需要优化

**解决方案**:
```python
# 1. 检查查询分析
from app.query.query_classifier import QueryClassifier
classifier = QueryClassifier(llm_client)
analysis = await classifier.classify(query)
print("查询分析:", analysis)
# 复杂度 < 7 时不会自动分解

# 2. 手动触发分解
from app.query.query_decomposer import QueryDecomposer
decomposer = QueryDecomposer(llm_client)
sub_queries = await decomposer.decompose(query, max_sub_queries=3)
print("子查询:", sub_queries)

# 3. 强制启用分解
result = await service.query(
    query=query,
    use_decomposition=True,  # 强制启用
)
```

---

## 📚 更多资源

- [完整文档](../../docs/RAG_ITER2_3_COMPLETION.md)
- [迭代计划](../../docs/RAG_ENGINE_ITERATION_PLAN.md)
- [Iter 1 使用指南](./ITER1_USAGE_GUIDE.md)
- [架构文档](../../docs/arch/overview.md)

---

## 💡 最佳实践总结

### 1. 功能选择

| 场景 | 推荐配置 |
|-----|---------|
| 简单问答 | Hybrid + Cache |
| 复杂推理 | Hybrid + Graph + Self-RAG |
| 长文档 | Hybrid + Compression |
| 多步任务 | Decomposition + Self-RAG |
| 低延迟 | Cache only, 禁用其他 |
| 高质量 | 全部启用 |

### 2. 参数建议

```python
# 平衡模式（推荐）
result = await service.query(
    query=query,
    top_k=5,
    use_graph=True,
    use_decomposition=True,
    use_self_rag=True,
    use_compression=True,
    compression_ratio=0.5,
    temperature=0.7,
)

# 高速模式
result = await service.query(
    query=query,
    top_k=3,
    use_graph=False,
    use_decomposition=False,
    use_self_rag=False,
    use_compression=False,
    temperature=0.7,
)

# 高质量模式
result = await service.query(
    query=query,
    top_k=10,
    use_graph=True,
    use_decomposition=True,
    use_self_rag=True,
    use_compression=False,
    temperature=0.3,
)
```

---

**版本**: v2.0
**更新日期**: 2025-10-29
