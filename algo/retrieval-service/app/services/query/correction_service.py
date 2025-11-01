"""
Query Correction Service - 查询纠错服务

功能:
- 拼写纠错 (SymSpell)
- 自定义词典
- 中英文混合支持

目标:
- 错误query准确率提升≥20%
- 纠错延迟≤20ms
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from app.observability.logging import logger


@dataclass
class CorrectionResult:
    """纠错结果"""

    original_query: str
    corrected_query: str
    corrections: list[tuple]  # (original_word, corrected_word)
    confidence: float
    latency_ms: float


class QueryCorrectionService:
    """查询纠错服务"""

    def __init__(
        self,
        dictionary_path: str = "data/spelling_dict.txt",
        max_edit_distance: int = 2,
        prefix_length: int = 7,
    ):
        """
        初始化查询纠错服务

        Args:
            dictionary_path: 词典路径
            max_edit_distance: 最大编辑距离
            prefix_length: 前缀长度
        """
        self.dictionary_path = dictionary_path
        self.max_edit_distance = max_edit_distance
        self.prefix_length = prefix_length

        # 初始化SymSpell（可选依赖）
        self.sym_spell = self._initialize_symspell()

        # 加载自定义词典
        self.custom_dict = self._load_custom_dictionary()

        logger.info(
            f"Query correction service initialized: "
            f"dict_size={len(self.custom_dict)}, "
            f"max_edit_distance={max_edit_distance}"
        )

    def _initialize_symspell(self):
        """初始化SymSpell"""
        try:
            from symspellpy import SymSpell

            sym_spell = SymSpell(
                max_dictionary_edit_distance=self.max_edit_distance,
                prefix_length=self.prefix_length,
            )

            # 加载内置词典
            dict_file = Path(self.dictionary_path)
            if dict_file.exists():
                sym_spell.load_dictionary(
                    str(dict_file),
                    term_index=0,
                    count_index=1,
                )
                logger.info(f"SymSpell dictionary loaded: {dict_file}")
            else:
                logger.warning(f"Dictionary not found: {dict_file}, using empty dict")

            return sym_spell

        except ImportError:
            logger.warning("SymSpellPy not installed. Install with: pip install symspellpy")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize SymSpell: {e}")
            return None

    def _load_custom_dictionary(self) -> set:
        """加载自定义词典"""
        custom_dict = set()

        try:
            dict_file = Path(self.dictionary_path)
            if dict_file.exists():
                with open(dict_file, encoding="utf-8") as f:
                    for line in f:
                        word = line.strip().split()[0]
                        if word:
                            custom_dict.add(word.lower())

            # 添加常见IT术语
            custom_dict.update(
                {
                    "python",
                    "java",
                    "javascript",
                    "docker",
                    "kubernetes",
                    "redis",
                    "mysql",
                    "mongodb",
                    "tensorflow",
                    "pytorch",
                    "machine learning",
                    "deep learning",
                    "neural network",
                    "api",
                    "restful",
                    "microservice",
                    "devops",
                    "ci/cd",
                }
            )

            logger.info(f"Custom dictionary loaded: {len(custom_dict)} words")
            return custom_dict

        except Exception as e:
            logger.warning(f"Failed to load custom dictionary: {e}")
            return set()

    async def correct(self, query: str) -> CorrectionResult:
        """
        纠错查询

        Args:
            query: 原始查询

        Returns:
            纠错结果
        """
        start_time = time.time()

        try:
            if self.sym_spell:
                # 使用SymSpell纠错
                corrected, corrections = self._symspell_correct(query)
            else:
                # 使用简单规则纠错
                corrected, corrections = self._simple_correct(query)

            latency_ms = (time.time() - start_time) * 1000

            result = CorrectionResult(
                original_query=query,
                corrected_query=corrected,
                corrections=corrections,
                confidence=0.9 if corrections else 1.0,
                latency_ms=latency_ms,
            )

            if corrections:
                logger.info(
                    f"Query corrected: '{query}' -> '{corrected}' "
                    f"({len(corrections)} corrections, {latency_ms:.1f}ms)"
                )

            return result

        except Exception as e:
            logger.error(f"Query correction failed: {e}", exc_info=True)
            return CorrectionResult(
                original_query=query,
                corrected_query=query,
                corrections=[],
                confidence=0.0,
                latency_ms=(time.time() - start_time) * 1000,
            )

    def _symspell_correct(self, query: str) -> tuple[str, list[tuple]]:
        """
        使用SymSpell纠错

        Args:
            query: 原始查询

        Returns:
            (纠正后的查询, 纠正列表)
        """
        if not self.sym_spell:
            return query, []

        try:
            # 查找建议
            suggestions = self.sym_spell.lookup_compound(
                query,
                max_edit_distance=self.max_edit_distance,
                transfer_casing=True,
            )

            if suggestions and suggestions[0].term != query:
                corrected = suggestions[0].term

                # 识别具体的纠正
                original_words = query.split()
                corrected_words = corrected.split()
                corrections = []

                for orig, corr in zip(original_words, corrected_words, strict=False):
                    if orig.lower() != corr.lower():
                        corrections.append((orig, corr))

                return corrected, corrections

            return query, []

        except Exception as e:
            logger.warning(f"SymSpell correction error: {e}")
            return query, []

    def _simple_correct(self, query: str) -> tuple[str, list[tuple]]:
        """
        简单规则纠错

        Args:
            query: 原始查询

        Returns:
            (纠正后的查询, 纠正列表)
        """
        # 常见错误映射
        common_errors = {
            "phyton": "python",
            "javasript": "javascript",
            "dokcer": "docker",
            "kubernets": "kubernetes",
            "machien": "machine",
            "learing": "learning",
            "netwrok": "network",
            "databse": "database",
        }

        words = query.split()
        corrected_words = []
        corrections = []

        for word in words:
            word_lower = word.lower()

            # 检查常见错误
            if word_lower in common_errors:
                corrected = common_errors[word_lower]
                corrected_words.append(corrected)
                corrections.append((word, corrected))
            else:
                corrected_words.append(word)

        corrected_query = " ".join(corrected_words)
        return corrected_query, corrections

    async def batch_correct(self, queries: list[str]) -> list[CorrectionResult]:
        """
        批量纠错

        Args:
            queries: 查询列表

        Returns:
            纠错结果列表
        """
        tasks = [self.correct(q) for q in queries]
        return await asyncio.gather(*tasks)

    def add_to_dictionary(self, words: list[str]):
        """
        添加到自定义词典

        Args:
            words: 词汇列表
        """
        for word in words:
            self.custom_dict.add(word.lower())

            if self.sym_spell:
                self.sym_spell.create_dictionary_entry(word, 1)

        logger.info(f"Added {len(words)} words to dictionary")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "symspell_available": self.sym_spell is not None,
            "custom_dict_size": len(self.custom_dict),
            "max_edit_distance": self.max_edit_distance,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = QueryCorrectionService()

        # 测试查询（包含拼写错误）
        test_queries = [
            "phyton programming tutorial",
            "machien learing basics",
            "dokcer container deployment",
            "javasript frameworks",
            "python programming",  # 正确拼写
        ]

        for query in test_queries:
            result = await service.correct(query)
            print(f"\n原查询: {result.original_query}")
            print(f"纠正后: {result.corrected_query}")
            if result.corrections:
                print(f"纠正项: {result.corrections}")
            print(f"延迟: {result.latency_ms:.1f}ms")

    asyncio.run(test())
