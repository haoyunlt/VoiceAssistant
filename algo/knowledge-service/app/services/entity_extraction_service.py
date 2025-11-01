"""
Entity and Relation Extraction Service
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """实体关系抽取服务"""

    def __init__(self, llm_client, ner_model=None):
        self.llm_client = llm_client
        self.ner_model = ner_model

    async def extract(self, text: str) -> dict[str, Any]:
        """抽取实体和关系"""
        # 1. 命名实体识别
        entities = await self._extract_entities(text)

        # 2. 关系抽取
        relations = await self._extract_relations(text, entities)

        # 3. 三元组构建
        triples = self._build_triples(entities, relations)

        return {"entities": entities, "relations": relations, "triples": triples}

    async def _extract_entities(self, text: str) -> list[dict]:
        """命名实体识别"""
        if self.ner_model:
            # 使用NER模型
            return await self._ner_with_model(text)
        else:
            # 使用LLM
            return await self._ner_with_llm(text)

    async def _ner_with_llm(self, text: str) -> list[dict]:
        """使用LLM进行NER"""
        prompt = f"""Extract named entities from the text:

Text: {text}

Return JSON array:
[
  {{"text": "entity1", "type": "PERSON", "span": [0, 7]}},
  {{"text": "entity2", "type": "ORG", "span": [10, 20]}}
]

Entity types: PERSON, ORG, LOC, DATE, PRODUCT, EVENT"""

        response = await self.llm_client.chat(
            [
                {"role": "system", "content": "You are a named entity recognition expert."},
                {"role": "user", "content": prompt},
            ]
        )

        import json

        try:
            entities = json.loads(response.get("content", "[]"))
            return entities
        except Exception:
            return []

    async def _ner_with_model(self, text: str) -> list[dict]:
        """使用NER模型"""
        entities = await self.ner_model.predict(text)
        return entities

    async def _extract_relations(self, text: str, entities: list[dict]) -> list[dict]:
        """关系抽取"""
        if len(entities) < 2:
            return []

        entity_texts = [e["text"] for e in entities]

        prompt = f"""Extract relationships between entities:

Text: {text}
Entities: {", ".join(entity_texts)}

Return JSON array:
[
  {{"subject": "entity1", "predicate": "works_for", "object": "entity2"}},
  {{"subject": "entity3", "predicate": "located_in", "object": "entity4"}}
]"""

        response = await self.llm_client.chat(
            [
                {"role": "system", "content": "You are a relation extraction expert."},
                {"role": "user", "content": prompt},
            ]
        )

        import json

        try:
            relations = json.loads(response.get("content", "[]"))
            return relations
        except Exception:
            return []

    def _build_triples(
        self, _entities: list[dict], relations: list[dict]
    ) -> list[tuple[str, str, str]]:
        """构建三元组"""
        triples = []
        for rel in relations:
            triple = (rel.get("subject", ""), rel.get("predicate", ""), rel.get("object", ""))
            if all(triple):
                triples.append(triple)
        return triples

    async def build_knowledge_graph(self, documents: list[str]) -> dict[str, Any]:
        """从文档构建知识图谱"""
        all_entities = []
        all_relations = []
        all_triples = []

        for doc in documents:
            result = await self.extract(doc)
            all_entities.extend(result["entities"])
            all_relations.extend(result["relations"])
            all_triples.extend(result["triples"])

        # 去重
        unique_entities = self._deduplicate_entities(all_entities)
        unique_relations = self._deduplicate_relations(all_relations)

        return {
            "entities": unique_entities,
            "relations": unique_relations,
            "triples": all_triples,
            "stats": {
                "entity_count": len(unique_entities),
                "relation_count": len(unique_relations),
                "triple_count": len(all_triples),
            },
        }

    def _deduplicate_entities(self, entities: list[dict]) -> list[dict]:
        """实体去重"""
        seen = set()
        unique = []
        for entity in entities:
            key = (entity.get("text", ""), entity.get("type", ""))
            if key not in seen:
                seen.add(key)
                unique.append(entity)
        return unique

    def _deduplicate_relations(self, relations: list[dict]) -> list[dict]:
        """关系去重"""
        seen = set()
        unique = []
        for rel in relations:
            key = (rel.get("subject", ""), rel.get("predicate", ""), rel.get("object", ""))
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        return unique
