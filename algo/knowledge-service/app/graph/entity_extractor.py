"""
Entity Extractor - 实体提取器

使用 NER 从文本中提取实体
"""

import re
from typing import Any, Dict, List, Optional

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EntityExtractor:
    """实体提取器"""

    def __init__(self, model: str = "en_core_web_sm"):
        """
        初始化实体提取器

        Args:
            model: SpaCy 模型名称
        """
        self.model_name = model
        self.nlp = None

        if not SPACY_AVAILABLE:
            logger.warning(
                "spacy not installed. Install with: pip install spacy && "
                "python -m spacy download en_core_web_sm"
            )
        else:
            try:
                self.nlp = spacy.load(model)
                logger.info(f"SpaCy model loaded: {model}")
            except OSError:
                logger.warning(
                    f"SpaCy model '{model}' not found. "
                    f"Download with: python -m spacy download {model}"
                )
                self.nlp = None

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        if not self.nlp:
            logger.warning("SpaCy model not available, using fallback")
            return self._fallback_extract(text)

        try:
            doc = self.nlp(text)

            entities = []
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 1.0,  # SpaCy doesn't provide confidence scores by default
                })

            logger.info(f"Extracted {len(entities)} entities from text")
            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._fallback_extract(text)

    def _fallback_extract(self, text: str) -> List[Dict[str, Any]]:
        """
        后备提取方法（基于简单规则）

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        entities = []

        # 提取大写开头的词组（可能是人名或地名）
        capitalized_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.finditer(capitalized_pattern, text)

        for match in matches:
            entities.append({
                "text": match.group(),
                "label": "UNKNOWN",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.5,
            })

        return entities

    def extract_with_context(
        self, text: str, context_window: int = 50
    ) -> List[Dict[str, Any]]:
        """
        提取实体并包含上下文

        Args:
            text: 输入文本
            context_window: 上下文窗口大小

        Returns:
            实体列表（包含上下文）
        """
        entities = self.extract_entities(text)

        for entity in entities:
            start = max(0, entity["start"] - context_window)
            end = min(len(text), entity["end"] + context_window)
            entity["context"] = text[start:end]

        return entities

    def group_by_label(
        self, entities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按标签分组实体

        Args:
            entities: 实体列表

        Returns:
            按标签分组的实体字典
        """
        grouped = {}
        for entity in entities:
            label = entity.get("label", "UNKNOWN")
            if label not in grouped:
                grouped[label] = []
            grouped[label].append(entity)

        return grouped


# 全局实例
_entity_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """
    获取实体提取器实例（单例）

    Returns:
        EntityExtractor 实例
    """
    global _entity_extractor

    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()

    return _entity_extractor
