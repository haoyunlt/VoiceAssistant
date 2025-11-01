"""
Enhanced GraphRAG Service - 增强版GraphRAG服务

集成所有优化功能：
- LLM缓存
- Token计量
- 错误处理与降级
- 实体链接
- 时序图谱
- 业务指标监控
"""

import logging
from datetime import datetime
from typing import Any

from app.common.exceptions import IndexBuildError
from app.common.fallback_handler import get_fallback_handler, get_llm_fallback_strategy
from app.core.metrics import (
    record_cache_access,
    record_entity_extraction,
    record_llm_call,
)
from app.core.token_counter import get_token_counter
from app.services.community_detection_gds import get_community_detection_gds
from app.services.entity_linking_service import get_entity_linking_service
from app.services.llm_cache_service import get_llm_cache_service
from app.services.temporal_graph_service import get_temporal_graph_service

logger = logging.getLogger(__name__)


class EnhancedGraphRAGService:
    """增强版GraphRAG服务"""

    def __init__(
        self,
        neo4j_client,
        llm_entity_extractor,
        embedding_service,
        redis_client,
        model_adapter_url: str = "http://model-adapter:8005",
        enable_cache: bool = True,
        enable_entity_linking: bool = True,
        enable_temporal: bool = False,
    ):
        """
        初始化增强版GraphRAG服务

        Args:
            neo4j_client: Neo4j客户端
            llm_entity_extractor: LLM实体提取器
            embedding_service: Embedding服务
            redis_client: Redis客户端
            model_adapter_url: 模型适配器URL
            enable_cache: 是否启用缓存
            enable_entity_linking: 是否启用实体链接
            enable_temporal: 是否启用时序图谱
        """
        self.neo4j = neo4j_client
        self.extractor = llm_entity_extractor
        self.embedding_service = embedding_service
        self.model_adapter_url = model_adapter_url

        # 功能开关
        self.enable_cache = enable_cache
        self.enable_entity_linking = enable_entity_linking
        self.enable_temporal = enable_temporal

        # 初始化组件
        self.cache_service = get_llm_cache_service(redis_client) if enable_cache else None
        self.token_counter = get_token_counter()
        self.fallback_handler = get_fallback_handler()
        self.llm_strategy = get_llm_fallback_strategy()

        # 增强功能服务
        self.entity_linking = (
            get_entity_linking_service(neo4j_client, embedding_service)
            if enable_entity_linking
            else None
        )
        self.community_detection_gds = get_community_detection_gds(neo4j_client)
        self.temporal_service = (
            get_temporal_graph_service(neo4j_client) if enable_temporal else None
        )

    async def build_index_with_enhancements(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        domain: str = "general",
        use_gds: bool = True,
    ) -> dict[str, Any]:
        """
        构建增强版索引

        Args:
            document_id: 文档ID
            chunks: 文本块列表
            domain: 领域
            use_gds: 是否使用Neo4j GDS进行社区检测

        Returns:
            索引构建结果
        """
        start_time = datetime.now()

        try:
            logger.info(
                f"Building enhanced index for document {document_id} with {len(chunks)} chunks"
            )

            # Step 1: 提取实体和关系（带缓存）
            entities, relations = await self._extract_with_cache(document_id, chunks, domain)

            # Step 2: 社区检测（使用GDS或降级到简单算法）
            if use_gds:
                try:
                    communities_result = (
                        await self.community_detection_gds.detect_communities_louvain(document_id)
                    )
                    communities = communities_result.get("communities", [])
                except Exception as e:
                    logger.warning(f"GDS community detection failed, using fallback: {e}")
                    communities_result = (
                        await self.community_detection_gds.detect_communities_fallback(document_id)
                    )
                    communities = communities_result.get("communities", [])
            else:
                communities_result = await self.community_detection_gds.detect_communities_fallback(
                    document_id
                )
                communities = communities_result.get("communities", [])

            # Step 3: 实体链接（合并重复实体）
            if self.enable_entity_linking and self.entity_linking:
                try:
                    linking_result = await self.entity_linking.link_entities_in_document(
                        document_id, method="hybrid"
                    )
                    logger.info(
                        f"Entity linking: merged {linking_result.get('merged_count', 0)} entities"
                    )
                except Exception as e:
                    logger.warning(f"Entity linking failed: {e}")

            # Step 4: 生成社区摘要（带缓存）
            await self._generate_summaries_with_cache(communities, domain)

            duration = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "document_id": document_id,
                "entities_count": len(entities),
                "relations_count": len(relations),
                "communities_count": len(communities),
                "duration_seconds": duration,
                "enhancements": {
                    "cache_enabled": self.enable_cache,
                    "entity_linking_enabled": self.enable_entity_linking,
                    "gds_used": use_gds,
                },
            }

        except Exception as e:
            logger.error(f"Enhanced index build failed: {e}", exc_info=True)
            raise IndexBuildError(f"Failed to build enhanced index: {e}", document_id=document_id) from e

    async def _extract_with_cache(
        self, document_id: str, chunks: list[dict[str, Any]], domain: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """使用缓存的实体提取"""
        all_entities = []
        all_relations = []
        entity_dedup = set()

        for chunk in chunks:
            content = chunk["content"]

            # 尝试从缓存获取
            if self.enable_cache and self.cache_service:
                cached = await self.cache_service.get_extraction_result(content, domain)
                if cached:
                    record_cache_access("llm_extraction", hit=True)
                    logger.debug(f"Cache hit for chunk {chunk['chunk_id']}")

                    # 使用缓存结果
                    for entity in cached.get("entities", []):
                        entity_key = (entity["text"].lower(), entity["label"])
                        if entity_key not in entity_dedup:
                            entity_dedup.add(entity_key)
                            entity["chunk_id"] = chunk["chunk_id"]
                            entity["document_id"] = document_id
                            all_entities.append(entity)

                    for relation in cached.get("relations", []):
                        relation["chunk_id"] = chunk["chunk_id"]
                        relation["document_id"] = document_id
                        all_relations.append(relation)

                    continue

            # 缓存未命中，执行提取
            if self.enable_cache:
                record_cache_access("llm_extraction", hit=False)

            extraction_start = datetime.now()

            # 使用降级策略执行提取
            result = await self.fallback_handler.execute_with_fallback(
                component="llm_extraction",
                primary_func=self._extract_with_llm,
                fallback_func=self._extract_with_rules,
                fallback_value={"entities": [], "relations": []},
                content=content,
                domain=domain,
            )

            extraction_duration = (datetime.now() - extraction_start).total_seconds()

            # 记录指标
            record_entity_extraction(
                domain=domain,
                duration=extraction_duration,
                entity_count=len(result.get("entities", [])),
                relation_count=len(result.get("relations", [])),
                success=True,
            )

            # 保存到缓存
            if self.enable_cache and self.cache_service:
                await self.cache_service.set_extraction_result(content, domain, result)

            # 处理提取结果
            for entity in result.get("entities", []):
                entity_key = (entity["text"].lower(), entity["label"])
                if entity_key not in entity_dedup:
                    entity_dedup.add(entity_key)
                    entity["chunk_id"] = chunk["chunk_id"]
                    entity["document_id"] = document_id
                    all_entities.append(entity)

            for relation in result.get("relations", []):
                relation["chunk_id"] = chunk["chunk_id"]
                relation["document_id"] = document_id
                all_relations.append(relation)

        # 存储到Neo4j
        await self._store_to_neo4j(document_id, all_entities, all_relations)

        return all_entities, all_relations

    async def _extract_with_llm(self, content: str, domain: str) -> dict[str, Any]:
        """使用LLM提取实体（带Token计量）"""
        # 获取当前模型
        model = self.llm_strategy.get_current_model()

        # 计算prompt tokens
        prompt = self._build_extraction_prompt(content, domain)
        prompt_tokens = self.token_counter.count_tokens(prompt, model)

        extraction_start = datetime.now()

        # 调用LLM
        result = await self.extractor.extract_entities_with_relations(content, domain)

        extraction_duration = (datetime.now() - extraction_start).total_seconds()

        # 估算completion tokens（基于返回结果）
        result_text = str(result)
        completion_tokens = self.token_counter.count_tokens(result_text, model)

        # 计算成本
        cost = self.token_counter.estimate_cost(prompt_tokens, completion_tokens, model)

        # 记录指标
        record_llm_call(
            model=model,
            operation="extraction",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            duration=extraction_duration,
            success=True,
        )

        return result

    async def _extract_with_rules(self, content: str, _domain: str) -> dict[str, Any]:
        """规则基础提取（降级方案）"""
        logger.warning("Using rule-based extraction (fallback)")

        # 使用SpaCy等规则方法
        from app.graph.entity_extractor import get_entity_extractor

        rule_extractor = get_entity_extractor()
        entities = rule_extractor.extract_entities(content)

        return {"entities": entities, "relations": []}

    def _build_extraction_prompt(self, content: str, domain: str) -> str:
        """构建提取prompt"""
        # 简化版prompt构建
        return f"Extract entities and relations from the following {domain} text:\n\n{content}"

    async def _generate_summaries_with_cache(self, communities: list[dict[str, Any]], domain: str):
        """生成社区摘要（带缓存）"""
        for community in communities:
            community_id = community["id"]

            # 尝试从缓存获取
            if self.enable_cache and self.cache_service:
                cached_summary = await self.cache_service.get_community_summary(
                    community_id, domain
                )
                if cached_summary:
                    community["summary"] = cached_summary
                    record_cache_access("community_summary", hit=True)
                    continue

            record_cache_access("community_summary", hit=False)

            # 生成摘要
            summary = await self._generate_summary(community, domain)
            community["summary"] = summary

            # 保存到缓存
            if self.enable_cache and self.cache_service:
                await self.cache_service.set_community_summary(community_id, domain, summary)

    async def _generate_summary(self, community: dict[str, Any], _domain: str) -> str:
        """生成社区摘要"""
        # 简化版摘要生成
        entities_text = ", ".join([e["text"] for e in community["entities"][:10]])
        return f"Community with {community['size']} entities including: {entities_text}"

    async def _store_to_neo4j(
        self,
        document_id: str,
        entities: list[dict[str, Any]],
        _relations: list[dict[str, Any]],
    ):
        """存储到Neo4j"""
        # 存储实体
        for entity in entities:
            properties = {
                "text": entity["text"],
                "label": entity["label"],
                "document_id": document_id,
                "confidence": entity.get("confidence", 1.0),
            }

            # 如果启用时序图谱，添加时间戳
            if self.enable_temporal:
                properties["created_at"] = datetime.now().isoformat()

            await self.neo4j.create_node(label=entity["label"], properties=properties)

        # 存储关系
        # ... (简化)

    async def get_enhanced_statistics(self, document_id: str | None = None) -> dict[str, Any]:
        """获取增强版统计信息"""
        stats = {}

        # 基础统计
        stats["cache"] = self.cache_service.get_stats() if self.cache_service else {}

        # 降级状态
        stats["fallback"] = self.fallback_handler.get_status()

        # LLM模型信息
        stats["llm_model"] = self.llm_strategy.get_model_info()

        # 时序图谱统计
        if self.enable_temporal and self.temporal_service:
            stats["temporal"] = await self.temporal_service.get_temporal_statistics(document_id)

        return stats


# 全局实例
_enhanced_service: EnhancedGraphRAGService | None = None


def get_enhanced_graphrag_service(
    neo4j_client,
    llm_entity_extractor,
    embedding_service,
    redis_client,
    **kwargs,
) -> EnhancedGraphRAGService:
    """获取增强版GraphRAG服务实例"""
    global _enhanced_service

    if _enhanced_service is None:
        _enhanced_service = EnhancedGraphRAGService(
            neo4j_client,
            llm_entity_extractor,
            embedding_service,
            redis_client,
            **kwargs,
        )

    return _enhanced_service
