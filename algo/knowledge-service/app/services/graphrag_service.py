"""
GraphRAG Service - GraphRAG分层索引服务

参考Microsoft GraphRAG架构实现:
- Level 0: 原始文本块
- Level 1: 实体+关系
- Level 2: 社区检测
- Level 3: 社区摘要
- Level 4: 全局摘要
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class Community:
    """社区数据结构"""

    def __init__(
        self,
        id: str,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        level: int = 0,
    ):
        self.id = id
        self.entities = entities
        self.relations = relations
        self.level = level
        self.summary: str | None = None
        self.keywords: list[str] = []
        self.size = len(entities)


class GraphRAGService:
    """GraphRAG分层索引服务"""

    def __init__(
        self,
        neo4j_client,
        llm_entity_extractor,
        model_adapter_url: str = "http://model-adapter:8005",
        model_name: str = "gpt-4o-mini",
    ):
        """
        初始化GraphRAG服务

        Args:
            neo4j_client: Neo4j客户端
            llm_entity_extractor: LLM实体提取器
            model_adapter_url: 模型适配器URL
            model_name: 模型名称
        """
        self.neo4j = neo4j_client
        self.extractor = llm_entity_extractor
        self.model_adapter_url = model_adapter_url
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=120.0)

    async def build_hierarchical_index(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        domain: str = "general",
    ) -> dict[str, Any]:
        """
        构建分层索引

        Args:
            document_id: 文档ID
            chunks: 文本块列表 [{"chunk_id": "...", "content": "..."}]
            domain: 领域

        Returns:
            索引构建结果
        """
        start_time = datetime.now()
        logger.info(f"Building hierarchical index for document {document_id}")

        try:
            # Level 0: 存储原始文本块（已由indexing-service完成）
            logger.info(f"Level 0: {len(chunks)} text chunks")

            # Level 1: 提取实体和关系
            entities, relations = await self._extract_knowledge_graph(
                document_id, chunks, domain
            )
            logger.info(
                f"Level 1: Extracted {len(entities)} entities, {len(relations)} relations"
            )

            # Level 2: 社区检测
            communities = await self._detect_communities(document_id, entities, relations)
            logger.info(f"Level 2: Detected {len(communities)} communities")

            # Level 3: 生成社区摘要
            await self._generate_community_summaries(communities, domain)
            logger.info(f"Level 3: Generated summaries for {len(communities)} communities")

            # Level 4: 生成全局摘要
            global_summary = await self._generate_global_summary(
                document_id, communities, domain
            )
            logger.info("Level 4: Generated global summary")

            # 存储索引元数据
            await self._store_index_metadata(
                document_id,
                {
                    "chunks": len(chunks),
                    "entities": len(entities),
                    "relations": len(relations),
                    "communities": len(communities),
                    "global_summary": global_summary,
                    "domain": domain,
                    "indexed_at": start_time.isoformat(),
                },
            )

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Hierarchical index built for {document_id} in {elapsed:.2f}s"
            )

            return {
                "success": True,
                "document_id": document_id,
                "entities_count": len(entities),
                "relations_count": len(relations),
                "communities_count": len(communities),
                "global_summary": global_summary,
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            logger.error(f"Failed to build hierarchical index: {e}", exc_info=True)
            return {
                "success": False,
                "document_id": document_id,
                "error": str(e),
            }

    async def _extract_knowledge_graph(
        self, document_id: str, chunks: list[dict[str, Any]], domain: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """提取知识图谱（实体+关系）"""
        all_entities = []
        all_relations = []
        entity_dedup = set()  # 用于去重

        # 并行处理块（每批5个）
        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # 并行提取
            results = await asyncio.gather(
                *[
                    self.extractor.extract_entities_with_relations(
                        chunk["content"], domain
                    )
                    for chunk in batch
                ],
                return_exceptions=True,
            )

            # 合并结果
            for chunk, result in zip(batch, results, strict=False):
                if isinstance(result, Exception):
                    logger.error(f"Extraction failed for chunk: {result}")
                    continue

                # 去重实体
                for entity in result.get("entities", []):
                    entity_key = (entity["text"].lower(), entity["label"])
                    if entity_key not in entity_dedup:
                        entity_dedup.add(entity_key)
                        entity["chunk_id"] = chunk["chunk_id"]
                        entity["document_id"] = document_id
                        all_entities.append(entity)

                # 添加关系
                for relation in result.get("relations", []):
                    relation["chunk_id"] = chunk["chunk_id"]
                    relation["document_id"] = document_id
                    all_relations.append(relation)

        # 存储到Neo4j
        await self._store_to_neo4j(document_id, all_entities, all_relations)

        return all_entities, all_relations

    async def _store_to_neo4j(
        self, document_id: str, entities: list[dict], relations: list[dict]
    ):
        """存储实体和关系到Neo4j"""
        entity_id_map = {}

        # 创建实体节点
        for entity in entities:
            node_properties = {
                "text": entity["text"],
                "label": entity["label"],
                "confidence": entity["confidence"],
                "document_id": document_id,
                "chunk_id": entity.get("chunk_id"),
            }

            node_id = await self.neo4j.create_node(
                label=entity["label"], properties=node_properties
            )
            if node_id:
                entity_id_map[entity["text"]] = node_id

        # 创建关系
        for relation in relations:
            subject_id = entity_id_map.get(relation["subject"])
            object_id = entity_id_map.get(relation["object"])

            if subject_id and object_id:
                await self.neo4j.create_relationship(
                    from_id=subject_id,
                    to_id=object_id,
                    rel_type=relation["predicate"],
                    properties={"confidence": relation["confidence"]},
                )

    async def _detect_communities(
        self, document_id: str, entities: list[dict], relations: list[dict]
    ) -> list[Community]:
        """社区检测（Louvain算法）"""
        try:
            # 使用Neo4j的图数据科学库进行社区检测

            # 如果Neo4j GDS不可用，使用简单的连通分量算法
            communities = await self._simple_community_detection(document_id)

            logger.info(f"Detected {len(communities)} communities")
            return communities

        except Exception as e:
            logger.warning(f"Community detection failed: {e}, using fallback")
            return await self._simple_community_detection(document_id)

    async def _simple_community_detection(self, document_id: str) -> list[Community]:
        """简单社区检测（连通分量）"""
        # 获取文档的所有节点和关系
        query = """
        MATCH (n)
        WHERE n.document_id = $document_id
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE m.document_id = $document_id
        RETURN n, r, m
        """

        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        # 构建邻接表
        graph: dict[str, set[str]] = {}
        entities_map: dict[str, dict] = {}

        for record in results:
            node = record.get("n")
            if node:
                node_id = str(node.element_id)
                entities_map[node_id] = dict(node)
                if node_id not in graph:
                    graph[node_id] = set()

                related_node = record.get("m")
                if related_node:
                    related_id = str(related_node.element_id)
                    graph[node_id].add(related_id)

        # DFS找连通分量
        visited = set()
        communities = []

        def dfs(node_id: str, component: set[str]):
            visited.add(node_id)
            component.add(node_id)
            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    dfs(neighbor, component)

        for node_id in graph:
            if node_id not in visited:
                component = set()
                dfs(node_id, component)

                # 创建社区对象
                community_entities = [
                    entities_map[nid] for nid in component if nid in entities_map
                ]

                if len(community_entities) >= 2:  # 至少2个实体才算社区
                    community_id = hashlib.md5(
                        str(sorted(component)).encode()
                    ).hexdigest()[:16]

                    communities.append(
                        Community(
                            id=community_id,
                            entities=community_entities,
                            relations=[],  # 简化处理
                            level=0,
                        )
                    )

        return communities

    async def _generate_community_summaries(
        self, communities: list[Community], domain: str
    ):
        """为每个社区生成摘要"""
        # 并行生成摘要
        tasks = [
            self._generate_community_summary(community, domain)
            for community in communities
        ]

        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        for community, summary in zip(communities, summaries, strict=False):
            if isinstance(summary, Exception):
                logger.error(f"Summary generation failed: {summary}")
                community.summary = f"Community with {community.size} entities"
            else:
                community.summary = summary
                community.keywords = self._extract_keywords(summary)

        # 存储社区摘要到Neo4j
        await self._store_community_summaries(communities)

    async def generate_community_summary(
        self,
        community_id: str,
        entities: list[str],
        relations: list[dict],
        domain: str = "general"
    ) -> str:
        """
        生成社区摘要（公开方法供外部调用）
        
        Args:
            community_id: 社区 ID
            entities: 实体文本列表
            relations: 关系列表
            domain: 领域
            
        Returns:
            社区摘要文本
        """
        # 构建 Community 对象
        entity_dicts = [{"text": e, "label": "Entity"} for e in entities]
        community = Community(
            id=community_id,
            entities=entity_dicts,
            relations=relations,
            level=2
        )
        
        # 调用内部方法生成摘要
        return await self._generate_community_summary(community, domain)

    async def _generate_community_summary(
        self, community: Community, domain: str
    ) -> str:
        """生成单个社区的摘要（内部方法）"""
        # 准备实体和关系描述
        entities_desc = "\n".join(
            [f"- {e.get('text', 'Unknown')} ({e.get('label', 'UNKNOWN')})" for e in community.entities[:20]]  # 限制20个
        )

        prompt = f"""Summarize the following knowledge community in {domain} domain.

Entities in this community:
{entities_desc}

Generate a concise 2-3 sentence summary that:
1. Describes the main theme or topic of this community
2. Highlights key entities and their significance
3. Explains what connects these entities

Summary:"""

        try:
            response = await self._call_llm(prompt, temperature=0.3, max_tokens=200)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate community summary: {e}")
            return f"A community of {community.size} entities related to {domain}"

    async def _generate_global_summary(
        self, document_id: str, communities: list[Community], domain: str
    ) -> str:
        """生成全局摘要"""
        # 汇总所有社区摘要
        community_summaries = "\n\n".join(
            [
                f"Community {i+1} ({comm.size} entities): {comm.summary}"
                for i, comm in enumerate(communities[:10])  # 最多10个社区
            ]
        )

        prompt = f"""Generate a high-level summary of the following knowledge graph extracted from a document.

Domain: {domain}
Number of communities: {len(communities)}

Community summaries:
{community_summaries}

Generate a comprehensive 3-5 sentence summary that:
1. Describes the overall themes and topics covered
2. Highlights the most important concepts and relationships
3. Provides a holistic view of the knowledge contained in this document

Global summary:"""

        try:
            response = await self._call_llm(prompt, temperature=0.3, max_tokens=300)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate global summary: {e}")
            return f"A knowledge graph with {len(communities)} communities in {domain} domain"

    async def _call_llm(
        self, prompt: str, temperature: float = 0.3, max_tokens: int = 200
    ) -> str:
        """调用LLM生成文本"""
        try:
            response = await self.client.post(
                f"{self.model_adapter_url}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a knowledge summarization expert.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _extract_keywords(self, text: str, top_k: int = 5) -> list[str]:
        """从文本提取关键词（简单实现）"""
        # 移除标点符号，转小写，分词
        import re

        words = re.findall(r'\b\w+\b', text.lower())

        # 移除停用词
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "this",
            "that",
        }
        words = [w for w in words if w not in stopwords and len(w) > 3]

        # 统计词频
        from collections import Counter

        word_counts = Counter(words)

        return [word for word, count in word_counts.most_common(top_k)]

    async def _store_community_summaries(self, communities: list[Community]):
        """存储社区摘要到Neo4j"""
        for community in communities:
            # 创建社区节点
            await self.neo4j.execute_query(
                """
                CREATE (c:Community {
                    id: $id,
                    summary: $summary,
                    keywords: $keywords,
                    size: $size,
                    level: $level
                })
                """,
                {
                    "id": community.id,
                    "summary": community.summary,
                    "keywords": community.keywords,
                    "size": community.size,
                    "level": community.level,
                },
            )

    async def _store_index_metadata(self, document_id: str, metadata: dict[str, Any]):
        """存储索引元数据"""
        await self.neo4j.execute_query(
            """
            MERGE (d:DocumentIndex {document_id: $document_id})
            SET d += $metadata
            """,
            {"document_id": document_id, "metadata": metadata},
        )

    async def query_global(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """
        全局查询（基于社区摘要）

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            查询结果
        """
        # 获取所有社区摘要
        communities_result = await self.neo4j.execute_query(
            """
            MATCH (c:Community)
            RETURN c.id as id, c.summary as summary, c.keywords as keywords, c.size as size
            ORDER BY c.size DESC
            LIMIT 20
            """
        )

        communities_data = []
        for record in communities_result:
            communities_data.append(
                {
                    "id": record["id"],
                    "summary": record["summary"],
                    "keywords": record["keywords"],
                    "size": record["size"],
                }
            )

        # 使用LLM进行相关性匹配
        relevant_communities = await self._rank_communities(query, communities_data, top_k)

        return {
            "query": query,
            "relevant_communities": relevant_communities[:top_k],
            "total_communities": len(communities_data),
        }

    async def _rank_communities(
        self, query: str, communities: list[dict], top_k: int
    ) -> list[dict]:
        """根据查询排序社区（简单实现：关键词匹配）"""
        query_words = set(query.lower().split())

        scored_communities = []
        for community in communities:
            keywords = community.get("keywords", [])
            summary = community.get("summary", "")

            # 计算相关性得分（关键词重叠）
            keyword_overlap = len(query_words & set(keywords))
            summary_overlap = sum(1 for word in query_words if word in summary.lower())

            score = keyword_overlap * 2 + summary_overlap
            community["relevance_score"] = score
            scored_communities.append(community)

        # 按得分排序
        scored_communities.sort(key=lambda x: x["relevance_score"], reverse=True)

        return scored_communities[:top_k]

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局实例
_graphrag_service: GraphRAGService | None = None


def get_graphrag_service(
    neo4j_client, llm_entity_extractor
) -> GraphRAGService:
    """获取GraphRAG服务实例（单例）"""
    global _graphrag_service

    if _graphrag_service is None:
        _graphrag_service = GraphRAGService(neo4j_client, llm_entity_extractor)

    return _graphrag_service
