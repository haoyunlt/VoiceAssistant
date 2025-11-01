"""
Entity Extractor - 实体抽取器

从文本中抽取实体和关系，用于构建知识图谱
"""

import logging
import re

logger = logging.getLogger(__name__)


class EntityExtractor:
    """实体抽取器（简化版，可替换为 NER 模型）"""

    def __init__(self, llm_client=None):
        """
        初始化实体抽取器

        Args:
            llm_client: LLM 客户端（用于高质量抽取）
        """
        self.llm_client = llm_client
        logger.info("Entity extractor initialized")

    async def extract_entities_and_relations(
        self, text: str, use_llm: bool = False
    ) -> tuple[list[dict], list[dict]]:
        """
        抽取实体和关系

        Args:
            text: 输入文本
            use_llm: 是否使用 LLM（更准确但更慢）

        Returns:
            (entities, relations) 元组
        """
        if use_llm and self.llm_client:
            return await self._extract_with_llm(text)
        else:
            return self._extract_with_rules(text)

    async def _extract_with_llm(self, text: str) -> tuple[list[dict], list[dict]]:
        """
        使用 LLM 抽取实体和关系

        Returns:
            (entities, relations)
        """
        prompt = f"""从以下文本中抽取实体和关系。

文本：
{text}

请以 JSON 格式返回：
{{
    "entities": [
        {{"name": "实体名称", "type": "人物/组织/概念/其他"}},
        ...
    ],
    "relations": [
        {{"source": "实体1", "relation": "关系类型", "target": "实体2"}},
        ...
    ]
}}

JSON:"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt, temperature=0.3, max_tokens=1000
            )

            # 解析 JSON
            import json

            result = json.loads(response)
            entities = result.get("entities", [])
            relations = result.get("relations", [])

            logger.info(
                f"Extracted {len(entities)} entities and {len(relations)} relations with LLM"
            )
            return entities, relations

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            # 回退到规则方法
            return self._extract_with_rules(text)

    def _extract_with_rules(self, text: str) -> tuple[list[dict], list[dict]]:
        """
        使用规则抽取实体（简化版）

        Returns:
            (entities, relations)
        """
        entities = []
        relations = []

        # 简单的规则：抽取大写开头的词组作为实体
        # 实际应用中应使用 NER 模型（如 spaCy, HuggingFace Transformers）
        entity_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        found_entities = re.findall(entity_pattern, text)

        # 去重并创建实体
        unique_entities = list(set(found_entities))
        for entity_name in unique_entities:
            entities.append({"name": entity_name, "type": "Unknown"})

        # 简单的关系抽取（基于模式）
        # 模式：实体1 [关系词] 实体2
        relation_patterns = [
            (r"(\w+)\s+is\s+a\s+(\w+)", "is_a"),
            (r"(\w+)\s+has\s+(\w+)", "has"),
            (r"(\w+)\s+uses\s+(\w+)", "uses"),
            (r"(\w+)\s+的\s+(\w+)", "has"),
        ]

        for pattern, relation_type in relation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for source, target in matches:
                relations.append({"source": source, "relation": relation_type, "target": target})

        logger.debug(
            f"Extracted {len(entities)} entities and {len(relations)} relations with rules"
        )
        return entities, relations

    def extract_key_concepts(self, text: str, top_k: int = 10) -> list[str]:
        """
        抽取关键概念

        Args:
            text: 输入文本
            top_k: 返回前 k 个概念

        Returns:
            关键概念列表
        """
        # 简化实现：抽取名词性词组
        # 实际应使用 TF-IDF、TextRank 等方法

        # 分词（简单按空格分）
        words = text.split()

        # 过滤停用词（简化版）
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for"}
        filtered_words = [w for w in words if w.lower() not in stopwords and len(w) > 2]

        # 统计词频
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # 排序并返回 top-k
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        key_concepts = [word for word, freq in sorted_words[:top_k]]

        return key_concepts
