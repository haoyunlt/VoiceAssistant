"""
实体识别与关系抽取
支持多种 NER 模型和关系抽取策略
"""

import logging
import re
from typing import Any

# NLP 库
import spacy
from transformers import pipeline

logger = logging.getLogger(__name__)


class EntityExtractor:
    """实体识别器"""

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        use_transformer: bool = False,
        transformer_model: str = "dslim/bert-base-NER",
    ):
        """
        初始化实体识别器

        Args:
            model_name: spaCy 模型名称
            use_transformer: 是否使用 Transformer 模型
            transformer_model: Transformer 模型名称
        """
        self.use_transformer = use_transformer

        if use_transformer:
            # 使用 Transformer 模型
            logger.info(f"Loading transformer NER model: {transformer_model}")
            self.ner_pipeline = pipeline(
                "ner", model=transformer_model, aggregation_strategy="simple"
            )
        else:
            # 使用 spaCy 模型
            logger.info(f"Loading spaCy model: {model_name}")
            try:
                self.nlp = spacy.load(model_name)
            except OSError:
                logger.warning(f"Model {model_name} not found, downloading...")
                import subprocess

                subprocess.run(["python", "-m", "spacy", "download", model_name])
                self.nlp = spacy.load(model_name)

    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """
        从文本中提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表，每个实体包含: text, label, start, end, confidence
        """
        if self.use_transformer:
            return self._extract_with_transformer(text)
        else:
            return self._extract_with_spacy(text)

    def _extract_with_spacy(self, text: str) -> list[dict[str, Any]]:
        """使用 spaCy 提取实体"""
        doc = self.nlp(text)

        entities = []
        for ent in doc.ents:
            entities.append(
                {
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 1.0,  # spaCy 不提供置信度
                }
            )

        logger.debug(f"Extracted {len(entities)} entities using spaCy")
        return entities

    def _extract_with_transformer(self, text: str) -> list[dict[str, Any]]:
        """使用 Transformer 提取实体"""
        results = self.ner_pipeline(text)

        entities = []
        for result in results:
            entities.append(
                {
                    "text": result["word"],
                    "label": result["entity_group"],
                    "start": result["start"],
                    "end": result["end"],
                    "confidence": result["score"],
                }
            )

        logger.debug(f"Extracted {len(entities)} entities using Transformer")
        return entities

    def extract_entities_with_context(
        self, text: str, context_window: int = 50
    ) -> list[dict[str, Any]]:
        """
        提取实体并包含上下文

        Args:
            text: 输入文本
            context_window: 上下文窗口大小

        Returns:
            包含上下文的实体列表
        """
        entities = self.extract_entities(text)

        for entity in entities:
            start = max(0, entity["start"] - context_window)
            end = min(len(text), entity["end"] + context_window)
            entity["context"] = text[start:end]

        return entities


class RelationExtractor:
    """关系抽取器"""

    def __init__(self, use_llm: bool = False, llm_model: str = "gpt-3.5-turbo"):
        """
        初始化关系抽取器

        Args:
            use_llm: 是否使用 LLM 进行关系抽取
            llm_model: LLM 模型名称
        """
        self.use_llm = use_llm
        self.llm_model = llm_model

        # 预定义的关系类型
        self.relation_types = [
            "is_a",  # 是
            "part_of",  # 部分
            "located_in",  # 位于
            "works_for",  # 工作于
            "created_by",  # 创建者
            "owns",  # 拥有
            "related_to",  # 相关
            "caused_by",  # 原因
            "results_in",  # 结果
        ]

        # 关系模式（基于规则）
        self.relation_patterns = [
            (r"(.+) is a (.+)", "is_a"),
            (r"(.+) works for (.+)", "works_for"),
            (r"(.+) located in (.+)", "located_in"),
            (r"(.+) part of (.+)", "part_of"),
            (r"(.+) created by (.+)", "created_by"),
            (r"(.+) owns (.+)", "owns"),
        ]

    def extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        从文本和实体中提取关系

        Args:
            text: 输入文本
            entities: 已提取的实体列表

        Returns:
            关系列表，每个关系包含: source, target, relation, confidence
        """
        if self.use_llm:
            return self._extract_with_llm(text, entities)
        else:
            return self._extract_with_rules(text, entities)

    def _extract_with_rules(
        self, text: str, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """基于规则的关系抽取"""
        relations = []

        # 1. 基于模式匹配
        for pattern, relation_type in self.relation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    relations.append(
                        {
                            "source": match.group(1).strip(),
                            "target": match.group(2).strip(),
                            "relation": relation_type,
                            "confidence": 0.8,
                            "method": "rule_based",
                        }
                    )

        # 2. 基于实体共现
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1 :]:
                # 检查两个实体是否在同一句子中
                if self._in_same_sentence(text, entity1, entity2):
                    relations.append(
                        {
                            "source": entity1["text"],
                            "target": entity2["text"],
                            "relation": "related_to",
                            "confidence": 0.6,
                            "method": "co_occurrence",
                        }
                    )

        logger.debug(f"Extracted {len(relations)} relations using rules")
        return relations

    def _extract_with_llm(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """使用 LLM 的关系抽取"""
        # TODO: 实现 LLM 关系抽取
        # 这里需要调用 LLM API
        logger.warning("LLM relation extraction not implemented yet")
        return self._extract_with_rules(text, entities)

    def _in_same_sentence(
        self, _text: str, entity1: dict[str, Any], entity2: dict[str, Any]
    ) -> bool:
        """检查两个实体是否在同一句子中"""
        # 简化版：检查是否在 100 个字符内
        distance = abs(entity1["start"] - entity2["start"])
        return distance < 100


class GraphBuilder:
    """知识图谱构建器（增强版）"""

    def __init__(self):
        """初始化图谱构建器"""
        self.entity_extractor = EntityExtractor()
        self.relation_extractor = RelationExtractor()

    def build_graph_from_text(self, text: str, document_id: str, tenant_id: str) -> dict[str, Any]:
        """
        从文本构建知识图谱

        Args:
            text: 输入文本
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            图谱统计信息
        """
        logger.info(f"Building graph for document: {document_id}")

        # 1. 提取实体
        entities = self.entity_extractor.extract_entities(text)
        logger.info(f"Extracted {len(entities)} entities")

        # 2. 提取关系
        relations = self.relation_extractor.extract_relations(text, entities)
        logger.info(f"Extracted {len(relations)} relations")

        # 3. 去重和过滤
        entities = self._deduplicate_entities(entities)
        relations = self._filter_relations(relations)

        # 4. 返回统计
        stats = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "entity_count": len(entities),
            "relation_count": len(relations),
            "entity_types": self._count_entity_types(entities),
            "relation_types": self._count_relation_types(relations),
            "entities": entities,
            "relations": relations,
        }

        return stats

    def _deduplicate_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """去除重复实体"""
        seen = set()
        unique_entities = []

        for entity in entities:
            key = (entity["text"].lower(), entity["label"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def _filter_relations(
        self, relations: list[dict[str, Any]], min_confidence: float = 0.5
    ) -> list[dict[str, Any]]:
        """过滤低置信度关系"""
        return [r for r in relations if r["confidence"] >= min_confidence]

    def _count_entity_types(self, entities: list[dict[str, Any]]) -> dict[str, int]:
        """统计实体类型"""
        counts = {}
        for entity in entities:
            label = entity["label"]
            counts[label] = counts.get(label, 0) + 1
        return counts

    def _count_relation_types(self, relations: list[dict[str, Any]]) -> dict[str, int]:
        """统计关系类型"""
        counts = {}
        for relation in relations:
            rel_type = relation["relation"]
            counts[rel_type] = counts.get(rel_type, 0) + 1
        return counts


def community_detection(
    entities: list[dict[str, Any]], relations: list[dict[str, Any]], algorithm: str = "louvain"
) -> dict[str, list[str]]:
    """
    社区检测

    Args:
        entities: 实体列表
        relations: 关系列表
        algorithm: 算法名称 (louvain, label_propagation)

    Returns:
        社区字典 {community_id: [entity_ids]}
    """
    try:
        import networkx as nx
        from networkx.algorithms import community as nx_community

        # 构建图
        G = nx.Graph()

        # 添加节点
        for entity in entities:
            G.add_node(entity["text"], **entity)

        # 添加边
        for relation in relations:
            G.add_edge(
                relation["source"],
                relation["target"],
                relation=relation["relation"],
                weight=relation["confidence"],
            )

        # 社区检测
        if algorithm == "louvain":
            communities = nx_community.louvain_communities(G)
        elif algorithm == "label_propagation":
            communities = nx_community.label_propagation_communities(G)
        else:
            logger.warning(f"Unknown algorithm: {algorithm}, using louvain")
            communities = nx_community.louvain_communities(G)

        # 转换为字典格式
        community_dict = {}
        for i, community in enumerate(communities):
            community_dict[f"community_{i}"] = list(community)

        logger.info(f"Detected {len(community_dict)} communities")
        return community_dict

    except ImportError:
        logger.error("networkx is required for community detection")
        return {}
    except Exception as e:
        logger.error(f"Community detection failed: {e}")
        return {}
