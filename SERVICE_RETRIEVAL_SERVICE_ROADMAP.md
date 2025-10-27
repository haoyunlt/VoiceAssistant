# Retrieval Service 服务功能清单与迭代计划

## 服务概述

Retrieval Service 是混合检索服务，提供向量检索、BM25 检索、混合检索和重排序功能。

**技术栈**: FastAPI + Milvus + Elasticsearch + Sentence-Transformers

**端口**: 8003

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 核心检索
- ✅ 向量检索（Milvus）
- ✅ BM25 检索（示例）
- ✅ 混合检索（RRF 融合）
- ✅ 基础重排序

#### 2. API 接口
- ✅ `/api/v1/retrieval/vector` - 向量检索
- ✅ `/api/v1/retrieval/bm25` - BM25 检索
- ✅ `/api/v1/retrieval/hybrid` - 混合检索
- ✅ `/health` - 健康检查

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代1：2周）

#### 1. Elasticsearch 集成
**当前状态**: 未完整实现

**待实现**:

```python
# 文件: algo/retrieval-service/app/services/elasticsearch_service.py

from elasticsearch import AsyncElasticsearch
from typing import List, Dict

class ElasticsearchService:
    """Elasticsearch 服务"""
    
    def __init__(self):
        self.client = AsyncElasticsearch(
            hosts=[{
                'host': os.getenv('ELASTICSEARCH_HOST', 'localhost'),
                'port': int(os.getenv('ELASTICSEARCH_PORT', 9200)),
                'scheme': 'http'
            }]
        )
        self.index_prefix = "voicehelper"
    
    async def create_index(
        self,
        tenant_id: str,
        kb_id: str
    ):
        """创建索引"""
        index_name = self._get_index_name(tenant_id, kb_id)
        
        # 定义映射
        mappings = {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",  # 中文分词
                    "search_analyzer": "ik_smart"
                },
                "title": {
                    "type": "text",
                    "analyzer": "ik_max_word"
                },
                "metadata": {"type": "object"},
                "created_at": {"type": "date"}
            }
        }
        
        # 创建索引
        await self.client.indices.create(
            index=index_name,
            body={"mappings": mappings}
        )
        
        logger.info(f"Created ES index: {index_name}")
    
    async def index_document(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_id: str,
        document_id: str,
        content: str,
        metadata: Dict = None
    ):
        """索引文档"""
        index_name = self._get_index_name(tenant_id, kb_id)
        
        doc = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat()
        }
        
        await self.client.index(
            index=index_name,
            id=chunk_id,
            body=doc
        )
    
    async def search(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int = 50,
        filters: Dict = None
    ) -> List[Dict]:
        """BM25 搜索"""
        index_name = self._get_index_name(tenant_id, kb_id)
        
        # 构建查询
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "title^1.5"],
                    "type": "best_fields"
                }
            }
        ]
        
        # 添加过滤条件
        if filters:
            for key, value in filters.items():
                must_clauses.append({
                    "term": {f"metadata.{key}": value}
                })
        
        # 执行搜索
        response = await self.client.search(
            index=index_name,
            body={
                "query": {
                    "bool": {
                        "must": must_clauses
                    }
                },
                "size": top_k,
                "_source": ["chunk_id", "document_id", "content", "metadata"]
            }
        )
        
        # 提取结果
        results = []
        for hit in response['hits']['hits']:
            results.append({
                "chunk_id": hit['_source']['chunk_id'],
                "document_id": hit['_source']['document_id'],
                "content": hit['_source']['content'],
                "score": hit['_score'],
                "metadata": hit['_source'].get('metadata', {}),
                "source": "bm25"
            })
        
        return results
    
    async def bulk_index(
        self,
        tenant_id: str,
        kb_id: str,
        documents: List[Dict]
    ):
        """批量索引"""
        index_name = self._get_index_name(tenant_id, kb_id)
        
        # 构建批量操作
        bulk_body = []
        for doc in documents:
            bulk_body.append({
                "index": {
                    "_index": index_name,
                    "_id": doc["chunk_id"]
                }
            })
            bulk_body.append({
                "chunk_id": doc["chunk_id"],
                "document_id": doc["document_id"],
                "content": doc["content"],
                "metadata": doc.get("metadata", {}),
                "created_at": datetime.utcnow().isoformat()
            })
        
        # 执行批量操作
        response = await self.client.bulk(body=bulk_body)
        
        logger.info(f"Bulk indexed {len(documents)} documents")
        
        return response
    
    def _get_index_name(self, tenant_id: str, kb_id: str) -> str:
        """生成索引名称"""
        return f"{self.index_prefix}_{tenant_id}_{kb_id}"
```

**验收标准**:
- [ ] ES 连接正常
- [ ] 索引创建和管理
- [ ] BM25 搜索正常
- [ ] 支持中文分词

#### 2. 多模态检索
**当前状态**: 部分实现

**位置**: `algo/retrieval-service/app/services/multimodal_retrieval_service.py`

**待实现**:

```python
# 文件: algo/retrieval-service/app/services/multimodal_retrieval_service.py
# 当前TODO: 第301、313行 - 实际的图像/文本编码器，第383行 - 图像描述模型

from transformers import CLIPModel, CLIPProcessor
import torch

class MultimodalRetrievalService:
    """多模态检索服务"""
    
    def __init__(self):
        # 加载 CLIP 模型
        self.model_name = "openai/clip-vit-base-patch32"
        self.model = CLIPModel.from_pretrained(self.model_name)
        self.processor = CLIPProcessor.from_pretrained(self.model_name)
        
        self.milvus_client = MilvusClient()
        self.collection_name = "multimodal_embeddings"
    
    async def encode_image(self, image_data: bytes) -> List[float]:
        """编码图像为向量"""
        # 加载图像
        from PIL import Image
        import io
        
        image = Image.open(io.BytesIO(image_data))
        
        # 处理图像
        inputs = self.processor(
            images=image,
            return_tensors="pt"
        )
        
        # 生成嵌入
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
        
        # 归一化
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features[0].tolist()
    
    async def encode_text(self, text: str) -> List[float]:
        """编码文本为向量"""
        # 处理文本
        inputs = self.processor(
            text=[text],
            return_tensors="pt",
            padding=True
        )
        
        # 生成嵌入
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        
        # 归一化
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        return text_features[0].tolist()
    
    async def search_by_image(
        self,
        image_data: bytes,
        tenant_id: str,
        kb_id: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        以图搜图/文
        """
        # 编码图像
        image_embedding = await self.encode_image(image_data)
        
        # 向量搜索
        results = self.milvus_client.search(
            collection_name=self.collection_name,
            data=[image_embedding],
            limit=top_k,
            filter=f"tenant_id == '{tenant_id}' && kb_id == '{kb_id}'",
            output_fields=["chunk_id", "content", "content_type", "metadata"]
        )
        
        # 格式化结果
        formatted_results = []
        for hit in results[0]:
            formatted_results.append({
                "chunk_id": hit["chunk_id"],
                "content": hit["content"],
                "content_type": hit["content_type"],
                "score": hit["distance"],
                "metadata": hit.get("metadata", {})
            })
        
        return formatted_results
    
    async def search_by_text_for_images(
        self,
        query: str,
        tenant_id: str,
        kb_id: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        以文搜图
        """
        # 编码文本
        text_embedding = await self.encode_text(query)
        
        # 搜索图像
        results = self.milvus_client.search(
            collection_name=self.collection_name,
            data=[text_embedding],
            limit=top_k,
            filter=f"tenant_id == '{tenant_id}' && kb_id == '{kb_id}' && content_type == 'image'",
            output_fields=["chunk_id", "image_url", "description", "metadata"]
        )
        
        # 格式化
        formatted_results = []
        for hit in results[0]:
            formatted_results.append({
                "chunk_id": hit["chunk_id"],
                "image_url": hit["image_url"],
                "description": hit.get("description", ""),
                "score": hit["distance"],
                "metadata": hit.get("metadata", {})
            })
        
        return formatted_results
    
    async def index_multimodal_content(
        self,
        tenant_id: str,
        kb_id: str,
        content_id: str,
        content_type: str,  # 'text', 'image', 'mixed'
        text: Optional[str] = None,
        image_data: Optional[bytes] = None,
        metadata: Dict = None
    ):
        """
        索引多模态内容
        """
        embeddings = []
        
        # 编码内容
        if text and content_type in ['text', 'mixed']:
            text_emb = await self.encode_text(text)
            embeddings.append(text_emb)
        
        if image_data and content_type in ['image', 'mixed']:
            image_emb = await self.encode_image(image_data)
            embeddings.append(image_emb)
        
        # 混合模态：平均嵌入
        if len(embeddings) > 1:
            final_embedding = np.mean(embeddings, axis=0).tolist()
        else:
            final_embedding = embeddings[0]
        
        # 插入 Milvus
        data = [{
            "chunk_id": content_id,
            "tenant_id": tenant_id,
            "kb_id": kb_id,
            "embedding": final_embedding,
            "content_type": content_type,
            "content": text or "",
            "metadata": metadata or {}
        }]
        
        self.milvus_client.insert(
            collection_name=self.collection_name,
            data=data
        )
```

**验收标准**:
- [ ] CLIP 模型集成
- [ ] 以图搜图功能
- [ ] 以文搜图功能
- [ ] 混合模态检索

#### 3. 索引优化器
**当前状态**: 未实现

**位置**: `algo/retrieval-service/app/services/index_optimizer_service.py`

**待实现**:

```python
# 文件: algo/retrieval-service/app/services/index_optimizer_service.py

class IndexOptimizerService:
    """索引优化服务"""
    
    def __init__(self):
        self.milvus_client = MilvusClient()
        self.redis_client = redis.Redis()
    
    async def optimize_index(
        self,
        tenant_id: str,
        kb_id: str
    ):
        """
        优化索引
        1. 分析查询模式
        2. 调整索引参数
        3. 重建索引（如需要）
        """
        collection_name = f"kb_{tenant_id}_{kb_id}"
        
        # 1. 分析查询统计
        stats = await self._analyze_query_patterns(tenant_id, kb_id)
        
        # 2. 确定优化策略
        if stats["avg_top_k"] > 100:
            # 大 top_k 查询多，优化召回
            index_params = {
                "metric_type": "IP",
                "index_type": "HNSW",
                "params": {"M": 32, "efConstruction": 512}  # 提高精度
            }
        else:
            # 小 top_k 查询多，优化速度
            index_params = {
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 2048}  # 提高速度
            }
        
        # 3. 重建索引
        await self._rebuild_index(collection_name, index_params)
        
        logger.info(f"Optimized index for {collection_name}")
    
    async def _analyze_query_patterns(
        self,
        tenant_id: str,
        kb_id: str
    ) -> Dict:
        """分析查询模式"""
        # 从 Redis 获取查询统计
        key = f"query_stats:{tenant_id}:{kb_id}"
        
        stats_data = self.redis_client.hgetall(key)
        
        return {
            "total_queries": int(stats_data.get(b"total", 0)),
            "avg_top_k": float(stats_data.get(b"avg_top_k", 10)),
            "avg_latency_ms": float(stats_data.get(b"avg_latency", 0)),
            "cache_hit_rate": float(stats_data.get(b"cache_hit_rate", 0))
        }
    
    async def _rebuild_index(
        self,
        collection_name: str,
        index_params: Dict
    ):
        """重建索引"""
        # 删除旧索引
        self.milvus_client.drop_index(
            collection_name=collection_name,
            field_name="embedding"
        )
        
        # 创建新索引
        self.milvus_client.create_index(
            collection_name=collection_name,
            field_name="embedding",
            index_params=index_params
        )
        
        # 加载到内存
        self.milvus_client.load_collection(collection_name)
    
    async def auto_optimize_all(self):
        """自动优化所有索引（定时任务）"""
        # 获取所有集合
        collections = self.milvus_client.list_collections()
        
        for collection in collections:
            if collection.startswith("kb_"):
                # 解析 tenant_id 和 kb_id
                parts = collection.split("_")
                if len(parts) >= 3:
                    tenant_id = parts[1]
                    kb_id = parts[2]
                    
                    await self.optimize_index(tenant_id, kb_id)
```

**验收标准**:
- [ ] 查询模式分析
- [ ] 自动索引优化
- [ ] 性能提升明显

---

### 🔄 P1 - 高级功能（迭代2：1周）

#### 1. 图检索增强

```python
# 文件: algo/retrieval-service/app/services/graph_retrieval_service.py

from neo4j import AsyncGraphDatabase

class GraphRetrievalService:
    """图检索服务"""
    
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password")
            )
        )
    
    async def search_with_graph(
        self,
        query: str,
        tenant_id: str,
        kb_id: str,
        max_hops: int = 2
    ) -> List[Dict]:
        """
        基于知识图谱的检索
        1. 提取查询中的实体
        2. 在图中查找相关节点
        3. 遍历关系获取上下文
        """
        # 1. 提取实体
        entities = await self._extract_entities(query)
        
        # 2. 图查询
        async with self.driver.session() as session:
            results = await session.run("""
                MATCH (e:Entity)
                WHERE e.name IN $entities
                  AND e.tenant_id = $tenant_id
                  AND e.kb_id = $kb_id
                
                // 扩展关系
                MATCH path = (e)-[*1..%d]-(related)
                
                RETURN e, related, relationships(path)
                LIMIT 20
            """ % max_hops, 
                entities=entities,
                tenant_id=tenant_id,
                kb_id=kb_id
            )
            
            # 3. 聚合结果
            graph_results = await self._aggregate_graph_results(results)
        
        return graph_results
    
    async def hybrid_search_with_graph(
        self,
        query: str,
        tenant_id: str,
        kb_id: str,
        vector_results: List[Dict]
    ) -> List[Dict]:
        """
        混合检索：向量 + 图
        """
        # 获取图检索结果
        graph_results = await self.search_with_graph(
            query, tenant_id, kb_id
        )
        
        # 融合结果
        merged = self._merge_vector_and_graph(
            vector_results,
            graph_results
        )
        
        return merged
```

**验收标准**:
- [ ] Neo4j 集成
- [ ] 图遍历查询
- [ ] 向量+图混合检索

#### 2. 智能重排序

```python
# 文件: algo/retrieval-service/app/services/rerank_service.py

from sentence_transformers import CrossEncoder

class RerankService:
    """重排序服务"""
    
    def __init__(self):
        # Cross-Encoder
        self.cross_encoder = CrossEncoder(
            'cross-encoder/ms-marco-MiniLM-L-12-v2'
        )
        
        # LLM 重排序（可选）
        self.use_llm_rerank = os.getenv("USE_LLM_RERANK", "false") == "true"
    
    async def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 10,
        method: str = "cross-encoder"
    ) -> List[Dict]:
        """
        重排序文档
        """
        if method == "cross-encoder":
            return await self._cross_encoder_rerank(query, documents, top_k)
        elif method == "llm":
            return await self._llm_rerank(query, documents, top_k)
        else:
            raise ValueError(f"Unknown rerank method: {method}")
    
    async def _cross_encoder_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """Cross-Encoder 重排序"""
        # 准备输入
        pairs = [
            [query, doc["content"]]
            for doc in documents
        ]
        
        # 计算分数
        scores = self.cross_encoder.predict(pairs)
        
        # 排序
        for i, doc in enumerate(documents):
            doc["rerank_score"] = float(scores[i])
        
        reranked = sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True
        )
        
        return reranked[:top_k]
    
    async def _llm_rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """LLM 重排序"""
        # 构建 prompt
        doc_list = "\n\n".join([
            f"[{i+1}] {doc['content'][:200]}..."
            for i, doc in enumerate(documents)
        ])
        
        prompt = f"""
        查询: {query}
        
        文档列表:
        {doc_list}
        
        请根据相关性对文档进行排序，返回文档编号列表（从高到低）。
        只返回编号，用逗号分隔，例如: 3,1,5,2,4
        """
        
        # 调用 LLM
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MODEL_ADAPTER_URL}/api/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
            )
            result = response.json()
            
        # 解析排序
        order_str = result["choices"][0]["message"]["content"].strip()
        order = [int(x) - 1 for x in order_str.split(",")]
        
        # 重排序
        reranked = [documents[i] for i in order if i < len(documents)]
        
        return reranked[:top_k]
```

**验收标准**:
- [ ] Cross-Encoder 重排序
- [ ] LLM 重排序
- [ ] 排序质量提升

---

## 三、实施方案

### 阶段1：核心功能（Week 1-2）

#### Day 1-5: Elasticsearch 集成
1. ES 连接和索引管理
2. BM25 搜索实现
3. 中文分词配置
4. 测试

#### Day 6-10: 多模态检索
1. CLIP 模型集成
2. 图像/文本编码
3. 跨模态搜索
4. 测试

#### Day 11-14: 索引优化
1. 查询分析
2. 自动优化
3. 性能测试

### 阶段2：高级功能（Week 3）

#### Day 15-17: 图检索
1. Neo4j 集成
2. 图遍历查询
3. 混合检索

#### Day 18-21: 智能重排序
1. Cross-Encoder
2. LLM 重排序
3. 质量评估

---

## 四、验收标准

### 功能验收
- [ ] ES 集成完成
- [ ] 多模态检索正常
- [ ] 索引优化有效
- [ ] 图检索正常
- [ ] 重排序质量高

### 性能验收
- [ ] 向量检索 < 50ms
- [ ] BM25 检索 < 100ms
- [ ] 混合检索 < 150ms
- [ ] 重排序 < 500ms

### 质量验收
- [ ] Recall@10 > 0.9
- [ ] MRR > 0.7
- [ ] 所有 TODO 清理

---

## 总结

Retrieval Service 的主要待完成功能：

1. **Elasticsearch 集成**: 完整 BM25 检索
2. **多模态检索**: CLIP 跨模态搜索
3. **索引优化**: 自动调优
4. **图检索**: 知识图谱增强
5. **智能重排序**: Cross-Encoder 和 LLM

完成后将提供强大的混合检索能力。


