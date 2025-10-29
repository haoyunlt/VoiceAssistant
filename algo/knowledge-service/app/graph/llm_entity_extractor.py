"""
LLM Entity Extractor - LLM增强实体提取器

使用大语言模型进行高准确率的实体识别和关系抽取
支持Few-shot学习和Chain-of-Thought推理
"""

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMEntityExtractor:
    """基于LLM的实体提取器"""

    def __init__(
        self,
        model_adapter_url: str = "http://model-adapter:8005",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        """
        初始化LLM实体提取器

        Args:
            model_adapter_url: 模型适配器URL
            model_name: 模型名称
            temperature: 生成温度
            max_tokens: 最大token数
        """
        self.model_adapter_url = model_adapter_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = httpx.AsyncClient(timeout=60.0)

        # Few-shot示例
        self.few_shot_examples = self._get_few_shot_examples()

    def _get_few_shot_examples(self) -> str:
        """获取Few-shot示例"""
        return """Example 1:
Text: "Apple was founded by Steve Jobs and Steve Wozniak in Cupertino, California in 1976."
Entities:
- {"text": "Apple", "type": "ORGANIZATION", "confidence": 0.95}
- {"text": "Steve Jobs", "type": "PERSON", "confidence": 0.98}
- {"text": "Steve Wozniak", "type": "PERSON", "confidence": 0.98}
- {"text": "Cupertino", "type": "LOCATION", "confidence": 0.92}
- {"text": "California", "type": "LOCATION", "confidence": 0.95}
- {"text": "1976", "type": "DATE", "confidence": 0.90}

Example 2:
Text: "Google announced a new AI model called Gemini at their Mountain View headquarters."
Entities:
- {"text": "Google", "type": "ORGANIZATION", "confidence": 0.97}
- {"text": "Gemini", "type": "PRODUCT", "confidence": 0.93}
- {"text": "Mountain View", "type": "LOCATION", "confidence": 0.94}

Example 3:
Text: "The European Union passed GDPR regulations in 2018 to protect user privacy."
Entities:
- {"text": "European Union", "type": "ORGANIZATION", "confidence": 0.96}
- {"text": "GDPR", "type": "LAW", "confidence": 0.95}
- {"text": "2018", "type": "DATE", "confidence": 0.92}
"""

    async def extract_entities(
        self, text: str, domain: str = "general", language: str = "en"
    ) -> list[dict[str, Any]]:
        """
        从文本提取实体

        Args:
            text: 输入文本
            domain: 领域（general, tech, medical, finance等）
            language: 语言（en, zh）

        Returns:
            实体列表
        """
        try:
            # 构建提示词
            prompt = self._build_entity_extraction_prompt(text, domain, language)

            # 调用LLM
            response = await self._call_llm(prompt)

            # 解析结果
            entities = self._parse_entity_response(response)

            logger.info(
                f"LLM extracted {len(entities)} entities from text (domain={domain}, lang={language})"
            )
            return entities

        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}", exc_info=True)
            # 降级到规则提取
            return []

    def _build_entity_extraction_prompt(
        self, text: str, domain: str, language: str
    ) -> str:
        """构建实体提取提示词"""
        domain_instructions = {
            "general": "Extract common entities like persons, organizations, locations, dates, and products.",
            "tech": "Focus on technical entities: companies, products, programming languages, frameworks, technologies, and technical terms.",
            "medical": "Focus on medical entities: diseases, symptoms, medications, treatments, medical procedures, and anatomical terms.",
            "finance": "Focus on financial entities: companies, currencies, financial products, market terms, and economic indicators.",
        }

        instruction = domain_instructions.get(domain, domain_instructions["general"])

        lang_note = ""
        if language == "zh":
            lang_note = "\nNote: The text is in Chinese. Extract entities accordingly."

        prompt = f"""You are an expert entity extraction system. Extract named entities from the following text.

Domain: {domain}
Task: {instruction}{lang_note}

{self.few_shot_examples}

Now extract entities from this text:
Text: "{text}"

Requirements:
1. Identify all relevant named entities
2. Classify each entity by type: PERSON, ORGANIZATION, LOCATION, DATE, PRODUCT, LAW, TECHNOLOGY, DISEASE, MEDICATION, CURRENCY, etc.
3. Assign a confidence score (0.0-1.0) based on context clarity
4. Use the entity's canonical form (e.g., "Steve Jobs" not "Jobs")

Output format (JSON only, no markdown):
{{
  "entities": [
    {{"text": "entity name", "type": "ENTITY_TYPE", "confidence": 0.95, "context": "brief surrounding context"}}
  ]
}}

Think step by step:
1. Read the text carefully
2. Identify potential entities
3. Classify each entity
4. Assign confidence scores
5. Format as JSON

JSON output:"""

        return prompt

    async def extract_entities_with_relations(
        self, text: str, domain: str = "general"
    ) -> dict[str, Any]:
        """
        同时提取实体和关系

        Args:
            text: 输入文本
            domain: 领域

        Returns:
            包含entities和relations的字典
        """
        try:
            prompt = self._build_entity_relation_prompt(text, domain)
            response = await self._call_llm(prompt)
            result = self._parse_entity_relation_response(response)

            logger.info(
                f"LLM extracted {len(result.get('entities', []))} entities and "
                f"{len(result.get('relations', []))} relations"
            )
            return result

        except Exception as e:
            logger.error(f"LLM entity-relation extraction failed: {e}", exc_info=True)
            return {"entities": [], "relations": []}

    def _build_entity_relation_prompt(self, text: str, domain: str) -> str:
        """构建实体关系联合提取提示词"""
        prompt = f"""You are an expert knowledge graph extraction system. Extract entities AND relationships from the following text.

Domain: {domain}
Text: "{text}"

Example output:
{{
  "entities": [
    {{"text": "Apple", "type": "ORGANIZATION", "confidence": 0.95}},
    {{"text": "Steve Jobs", "type": "PERSON", "confidence": 0.98}},
    {{"text": "Cupertino", "type": "LOCATION", "confidence": 0.92}}
  ],
  "relations": [
    {{"subject": "Steve Jobs", "predicate": "FOUNDED", "object": "Apple", "confidence": 0.95}},
    {{"subject": "Apple", "predicate": "LOCATED_IN", "object": "Cupertino", "confidence": 0.90}}
  ]
}}

Relation types:
- FOUNDED, WORKS_AT, CEO_OF (person-org)
- LOCATED_IN, HEADQUARTERED_IN (org-location)
- ACQUIRED, PARTNERED_WITH, COMPETES_WITH (org-org)
- BORN_IN, EDUCATED_AT, INVENTED (person-related)
- PART_OF, SUBSIDIARY_OF, OWNED_BY (org hierarchy)
- CREATED, DEVELOPED, RELEASED (product-related)

Requirements:
1. Extract all entities with types and confidence
2. Extract all relationships between entities
3. Use canonical entity names (as they appear in entities list)
4. Only extract relationships that are explicitly stated or strongly implied
5. Assign confidence scores based on context clarity

Output JSON only (no markdown):"""

        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """
        调用LLM API

        Args:
            prompt: 提示词

        Returns:
            LLM响应文本
        """
        try:
            response = await self.client.post(
                f"{self.model_adapter_url}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert entity extraction system. Always respond with valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
                timeout=60.0,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            return content

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling model adapter: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise

    def _parse_entity_response(self, response: str) -> list[dict[str, Any]]:
        """解析实体提取响应"""
        try:
            # 移除可能的markdown代码块
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # 解析JSON
            data = json.loads(response)

            entities = []
            for entity_data in data.get("entities", []):
                entities.append(
                    {
                        "text": entity_data["text"],
                        "label": entity_data.get("type", "UNKNOWN"),
                        "confidence": entity_data.get("confidence", 0.8),
                        "context": entity_data.get("context", ""),
                    }
                )

            return entities

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse entity JSON: {e}\nResponse: {response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing entity response: {e}")
            return []

    def _parse_entity_relation_response(self, response: str) -> dict[str, Any]:
        """解析实体关系联合响应"""
        try:
            # 清理响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)

            # 解析实体
            entities = []
            for entity_data in data.get("entities", []):
                entities.append(
                    {
                        "text": entity_data["text"],
                        "label": entity_data.get("type", "UNKNOWN"),
                        "confidence": entity_data.get("confidence", 0.8),
                    }
                )

            # 解析关系
            relations = []
            for relation_data in data.get("relations", []):
                relations.append(
                    {
                        "subject": relation_data["subject"],
                        "predicate": relation_data["predicate"],
                        "object": relation_data["object"],
                        "confidence": relation_data.get("confidence", 0.8),
                    }
                )

            return {"entities": entities, "relations": relations}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nResponse: {response}")
            return {"entities": [], "relations": []}
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {"entities": [], "relations": []}

    async def batch_extract(
        self, texts: list[str], domain: str = "general", batch_size: int = 5
    ) -> list[list[dict[str, Any]]]:
        """
        批量提取实体

        Args:
            texts: 文本列表
            domain: 领域
            batch_size: 批次大小

        Returns:
            实体列表的列表
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # 并行处理批次
            import asyncio

            batch_results = await asyncio.gather(
                *[self.extract_entities(text, domain) for text in batch],
                return_exceptions=True,
            )

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch extraction error: {result}")
                    results.append([])
                else:
                    results.append(result)

        return results

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局实例
_llm_entity_extractor: LLMEntityExtractor | None = None


def get_llm_entity_extractor(
    model_adapter_url: str = None, model_name: str = None
) -> LLMEntityExtractor:
    """
    获取LLM实体提取器实例（单例）

    Args:
        model_adapter_url: 模型适配器URL
        model_name: 模型名称

    Returns:
        LLMEntityExtractor实例
    """
    global _llm_entity_extractor

    if _llm_entity_extractor is None:
        _llm_entity_extractor = LLMEntityExtractor(
            model_adapter_url=model_adapter_url
            or "http://model-adapter:8005",
            model_name=model_name or "gpt-4o-mini",
        )

    return _llm_entity_extractor
