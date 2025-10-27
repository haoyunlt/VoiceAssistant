"""
NER (Named Entity Recognition) 服务
支持多种 NER 模型：SpaCy, HanLP, LLM-based
"""

import logging
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class NERBackend(str, Enum):
    """NER 后端类型"""
    SPACY = "spacy"
    HANLP = "hanlp"
    LLM = "llm"
    JIEBA = "jieba"  # 简单分词后备


class Entity:
    """实体对象"""
    def __init__(self, text: str, label: str, start: int, end: int, score: float = 1.0):
        self.text = text
        self.label = label
        self.start = start
        self.end = end
        self.score = score

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "score": self.score
        }


class NERService:
    """NER 服务（支持多后端）"""

    def __init__(self, backend: str = "spacy", language: str = "zh"):
        """
        初始化 NER 服务

        Args:
            backend: NER 后端（spacy/hanlp/llm/jieba）
            language: 语言（zh/en）
        """
        self.backend = backend
        self.language = language
        self.model = None

        logger.info(f"NER Service initialized with backend={backend}, language={language}")

    async def initialize(self):
        """初始化 NER 模型"""
        try:
            if self.backend == NERBackend.SPACY:
                await self._init_spacy()
            elif self.backend == NERBackend.HANLP:
                await self._init_hanlp()
            elif self.backend == NERBackend.LLM:
                await self._init_llm()
            elif self.backend == NERBackend.JIEBA:
                await self._init_jieba()
            else:
                raise ValueError(f"Unsupported NER backend: {self.backend}")

            logger.info(f"NER model loaded successfully: {self.backend}")
        except Exception as e:
            logger.warning(f"Failed to load NER model {self.backend}: {e}, falling back to jieba")
            self.backend = NERBackend.JIEBA
            await self._init_jieba()

    async def _init_spacy(self):
        """初始化 SpaCy 模型"""
        try:
            import spacy

            # 加载中文模型
            if self.language == "zh":
                model_name = "zh_core_web_sm"
                try:
                    self.model = spacy.load(model_name)
                except OSError:
                    logger.info(f"Downloading SpaCy model: {model_name}")
                    import subprocess
                    subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
                    self.model = spacy.load(model_name)
            else:
                model_name = "en_core_web_sm"
                try:
                    self.model = spacy.load(model_name)
                except OSError:
                    logger.info(f"Downloading SpaCy model: {model_name}")
                    import subprocess
                    subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
                    self.model = spacy.load(model_name)

        except ImportError:
            raise ImportError("spacy not installed. Run: pip install spacy")

    async def _init_hanlp(self):
        """初始化 HanLP 模型"""
        try:
            import hanlp

            # 使用轻量级模型
            self.model = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH)

        except ImportError:
            raise ImportError("hanlp not installed. Run: pip install hanlp")

    async def _init_llm(self):
        """初始化 LLM-based NER"""
        # 使用 LLM API 进行 NER
        # 需要配置 LLM 客户端
        self.model = "llm"  # 占位符
        logger.info("LLM-based NER initialized")

    async def _init_jieba(self):
        """初始化 Jieba（后备方案）"""
        import jieba
        import jieba.posseg as pseg

        self.model = pseg
        logger.info("Jieba NER initialized (fallback)")

    async def extract_entities(self, text: str, filter_labels: Optional[List[str]] = None) -> List[Entity]:
        """
        从文本中提取实体

        Args:
            text: 输入文本
            filter_labels: 过滤的实体类型（如果为None，返回所有类型）

        Returns:
            实体列表
        """
        if not text or not text.strip():
            return []

        try:
            if self.backend == NERBackend.SPACY:
                return await self._extract_with_spacy(text, filter_labels)
            elif self.backend == NERBackend.HANLP:
                return await self._extract_with_hanlp(text, filter_labels)
            elif self.backend == NERBackend.LLM:
                return await self._extract_with_llm(text, filter_labels)
            elif self.backend == NERBackend.JIEBA:
                return await self._extract_with_jieba(text, filter_labels)
            else:
                return []
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}", exc_info=True)
            return []

    async def _extract_with_spacy(self, text: str, filter_labels: Optional[List[str]]) -> List[Entity]:
        """使用 SpaCy 提取实体"""
        doc = self.model(text)

        entities = []
        for ent in doc.ents:
            # 过滤实体类型
            if filter_labels and ent.label_ not in filter_labels:
                continue

            entities.append(Entity(
                text=ent.text,
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                score=1.0
            ))

        return entities

    async def _extract_with_hanlp(self, text: str, filter_labels: Optional[List[str]]) -> List[Entity]:
        """使用 HanLP 提取实体"""
        result = self.model(text, tasks='ner')

        entities = []
        if 'ner' in result:
            ner_results = result['ner']
            for ent_text, ent_label in ner_results:
                # 过滤实体类型
                if filter_labels and ent_label not in filter_labels:
                    continue

                # 查找实体在原文中的位置
                start = text.find(ent_text)
                if start >= 0:
                    entities.append(Entity(
                        text=ent_text,
                        label=ent_label,
                        start=start,
                        end=start + len(ent_text),
                        score=1.0
                    ))

        return entities

    async def _extract_with_llm(self, text: str, filter_labels: Optional[List[str]]) -> List[Entity]:
        """使用 LLM 提取实体"""
        # TODO: 实现 LLM API 调用
        # 可以使用 OpenAI Function Calling 或 prompt engineering

        # 占位实现
        logger.warning("LLM-based NER not fully implemented yet")
        return []

    async def _extract_with_jieba(self, text: str, filter_labels: Optional[List[str]]) -> List[Entity]:
        """使用 Jieba 提取实体（简化方案）"""
        import jieba.posseg as pseg

        # 使用词性标注提取名词性词语作为实体
        words = pseg.cut(text)

        # 名词性词性标记
        noun_pos = {'n', 'nr', 'ns', 'nt', 'nz', 'ng'}  # 名词、人名、地名、机构名等

        entities = []
        start_pos = 0

        for word, pos in words:
            if pos[0] in {'n', 'v'} and len(word) >= 2:  # 名词或动词，且长度>=2
                # 简单映射词性到实体类型
                label = "ENTITY"
                if pos == "nr":
                    label = "PERSON"
                elif pos == "ns":
                    label = "LOCATION"
                elif pos == "nt":
                    label = "ORGANIZATION"

                # 过滤实体类型
                if filter_labels and label not in filter_labels:
                    start_pos += len(word)
                    continue

                entities.append(Entity(
                    text=word,
                    label=label,
                    start=start_pos,
                    end=start_pos + len(word),
                    score=0.8  # Jieba 置信度较低
                ))

            start_pos += len(word)

        return entities

    async def extract_entity_names(self, text: str, min_length: int = 2) -> List[str]:
        """
        提取实体名称列表（简化接口）

        Args:
            text: 输入文本
            min_length: 最小实体长度

        Returns:
            实体名称列表（去重）
        """
        entities = await self.extract_entities(text)

        # 去重并过滤短实体
        entity_names = list(set([
            ent.text for ent in entities
            if len(ent.text) >= min_length
        ]))

        return entity_names

    def get_supported_labels(self) -> List[str]:
        """获取支持的实体类型"""
        if self.backend == NERBackend.SPACY:
            if self.language == "zh":
                return ["PERSON", "LOC", "ORG", "GPE", "DATE", "TIME"]
            else:
                return ["PERSON", "NORP", "FAC", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "DATE", "TIME"]
        elif self.backend == NERBackend.HANLP:
            return ["PER", "LOC", "ORG"]
        elif self.backend == NERBackend.JIEBA:
            return ["PERSON", "LOCATION", "ORGANIZATION", "ENTITY"]
        else:
            return []


# 全局 NER 服务实例
_ner_service_instance: Optional[NERService] = None


async def get_ner_service(backend: str = "jieba", language: str = "zh") -> NERService:
    """
    获取 NER 服务单例

    Args:
        backend: NER 后端
        language: 语言

    Returns:
        NER 服务实例
    """
    global _ner_service_instance

    if _ner_service_instance is None:
        _ner_service_instance = NERService(backend=backend, language=language)
        await _ner_service_instance.initialize()

    return _ner_service_instance
