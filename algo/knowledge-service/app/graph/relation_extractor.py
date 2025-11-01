"""
Relation Extractor - 关系提取器

从文本中提取实体之间的关系
"""

import re
from typing import Any

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

import logging

logger = logging.getLogger(__name__)


class RelationExtractor:
    """关系提取器"""

    def __init__(self, model: str = "en_core_web_sm"):
        """
        初始化关系提取器

        Args:
            model: SpaCy 模型名称
        """
        self.model_name = model
        self.nlp = None

        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load(model)
                logger.info(f"SpaCy model loaded for relation extraction: {model}")
            except OSError:
                logger.warning(f"SpaCy model '{model}' not found")
                self.nlp = None

    def extract_relations(
        self, text: str, entities: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        从文本提取关系

        Args:
            text: 输入文本
            entities: 已提取的实体列表（可选）

        Returns:
            关系列表
        """
        if not self.nlp:
            logger.warning("SpaCy model not available, using fallback")
            return self._fallback_extract(text, entities)

        try:
            doc = self.nlp(text)
            relations = []

            # 使用依存句法分析提取关系
            for sent in doc.sents:
                for token in sent:
                    # 查找动词作为关系
                    if token.pos_ == "VERB":
                        # 查找主语
                        subject = None
                        for child in token.children:
                            if child.dep_ in ("nsubj", "nsubjpass"):
                                subject = child
                                break

                        # 查找宾语
                        obj = None
                        for child in token.children:
                            if child.dep_ in ("dobj", "pobj", "attr"):
                                obj = child
                                break

                        # 如果找到主语和宾语，创建关系
                        if subject and obj:
                            relations.append(
                                {
                                    "subject": self._expand_entity(subject),
                                    "predicate": token.text,
                                    "object": self._expand_entity(obj),
                                    "confidence": 0.8,
                                }
                            )

            logger.info(f"Extracted {len(relations)} relations from text")
            return relations

        except Exception as e:
            logger.error(f"Relation extraction failed: {e}")
            return self._fallback_extract(text, entities)

    def _expand_entity(self, token) -> str:
        """
        扩展实体以包含修饰词

        Args:
            token: SpaCy token

        Returns:
            完整实体文本
        """
        # 获取所有子孙节点
        subtree = list(token.subtree)
        # 按位置排序
        subtree.sort(key=lambda t: t.i)
        # 合并文本
        return " ".join(t.text for t in subtree)

    def _fallback_extract(
        self, text: str, _entities: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        后备提取方法（基于简单规则）

        Args:
            text: 输入文本
            entities: 已提取的实体列表

        Returns:
            关系列表
        """
        relations = []

        # 简单的 SVO 模式匹配
        # Pattern: Entity1 动词 Entity2
        patterns = [
            r"(\w+(?:\s+\w+)*)\s+(is|are|was|were|has|have|owns|creates|manages)\s+(\w+(?:\s+\w+)*)",
            r"(\w+(?:\s+\w+)*)\s+(works\s+for|belongs\s+to|located\s+in)\s+(\w+(?:\s+\w+)*)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                relations.append(
                    {
                        "subject": match.group(1).strip(),
                        "predicate": match.group(2).strip(),
                        "object": match.group(3).strip(),
                        "confidence": 0.5,
                    }
                )

        return relations

    def extract_triplets(self, text: str) -> list[tuple[str, str, str]]:
        """
        提取 (主语, 关系, 宾语) 三元组

        Args:
            text: 输入文本

        Returns:
            三元组列表
        """
        relations = self.extract_relations(text)

        triplets = [(rel["subject"], rel["predicate"], rel["object"]) for rel in relations]

        return triplets

    def filter_by_confidence(
        self, relations: list[dict[str, Any]], min_confidence: float = 0.5
    ) -> list[dict[str, Any]]:
        """
        按置信度过滤关系

        Args:
            relations: 关系列表
            min_confidence: 最小置信度

        Returns:
            过滤后的关系列表
        """
        return [rel for rel in relations if rel.get("confidence", 0) >= min_confidence]


# 全局实例
_relation_extractor: RelationExtractor | None = None


def get_relation_extractor() -> RelationExtractor:
    """
    获取关系提取器实例（单例）

    Returns:
        RelationExtractor 实例
    """
    global _relation_extractor

    if _relation_extractor is None:
        _relation_extractor = RelationExtractor()

    return _relation_extractor
