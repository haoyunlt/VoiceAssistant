"""
分块质量评估
评估分块的完整性、连贯性和质量
"""

import logging
import re
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ChunkQualityEvaluator:
    """分块质量评估器"""

    def __init__(
        self,
        min_score: float = 0.7,
        weights: dict[str, float] | None = None,
    ):
        """
        初始化质量评估器

        Args:
            min_score: 最低质量分数
            weights: 各项指标权重
        """
        self.min_score = min_score

        # 默认权重
        self.weights = weights or {
            "completeness": 0.3,  # 完整性
            "coherence": 0.3,     # 连贯性
            "size": 0.2,          # 大小合理性
            "overlap": 0.2,       # 重叠度
        }

        logger.info(f"ChunkQualityEvaluator initialized: min_score={min_score}")

    async def evaluate(
        self,
        chunks: list[dict[str, Any]],
        original_text: str | None = None,
    ) -> dict[str, Any]:
        """
        评估分块质量

        Args:
            chunks: 分块列表
            original_text: 原始文本

        Returns:
            质量评估结果
        """
        if not chunks:
            return {
                "overall_score": 0.0,
                "is_acceptable": False,
                "issues": ["No chunks provided"],
            }

        # 1. 完整性检查
        completeness_score = self._evaluate_completeness(chunks, original_text)

        # 2. 连贯性检查
        coherence_score = self._evaluate_coherence(chunks)

        # 3. 大小合理性检查
        size_score = self._evaluate_size(chunks)

        # 4. 重叠度检查
        overlap_score = self._evaluate_overlap(chunks)

        # 计算总分
        overall_score = (
            self.weights["completeness"] * completeness_score
            + self.weights["coherence"] * coherence_score
            + self.weights["size"] * size_score
            + self.weights["overlap"] * overlap_score
        )

        # 识别问题
        issues = []
        if completeness_score < 0.9:
            issues.append(f"Completeness score low: {completeness_score:.2f}")
        if coherence_score < 0.8:
            issues.append(f"Coherence score low: {coherence_score:.2f}")
        if size_score < 0.7:
            issues.append(f"Size distribution poor: {size_score:.2f}")
        if overlap_score < 0.6:
            issues.append(f"Overlap pattern unusual: {overlap_score:.2f}")

        result = {
            "overall_score": overall_score,
            "is_acceptable": overall_score >= self.min_score,
            "scores": {
                "completeness": completeness_score,
                "coherence": coherence_score,
                "size": size_score,
                "overlap": overlap_score,
            },
            "statistics": {
                "total_chunks": len(chunks),
                "avg_chunk_size": np.mean([len(c["content"]) for c in chunks]),
                "std_chunk_size": np.std([len(c["content"]) for c in chunks]),
                "min_chunk_size": min(len(c["content"]) for c in chunks),
                "max_chunk_size": max(len(c["content"]) for c in chunks),
            },
            "issues": issues,
            "recommendations": self._generate_recommendations(
                completeness_score,
                coherence_score,
                size_score,
                overlap_score,
            ),
        }

        logger.info(
            f"Quality evaluation: overall={overall_score:.2f}, "
            f"acceptable={result['is_acceptable']}, "
            f"issues={len(issues)}"
        )

        return result

    def _evaluate_completeness(
        self,
        chunks: list[dict[str, Any]],
        original_text: str | None,
    ) -> float:
        """
        评估完整性（是否保留了原文的所有重要信息）

        策略:
        1. 检查句子完整性（没有被截断）
        2. 检查总长度与原文的比例

        Args:
            chunks: 分块列表
            original_text: 原始文本

        Returns:
            完整性分数 (0-1)
        """
        scores = []

        # 1. 句子完整性检查
        sentence_completeness = self._check_sentence_completeness(chunks)
        scores.append(sentence_completeness)

        # 2. 长度比例检查
        if original_text:
            total_chunk_length = sum(len(c["content"]) for c in chunks)
            length_ratio = total_chunk_length / len(original_text)

            # 理想情况应该接近1（考虑重叠，可能略大于1）
            if 0.9 <= length_ratio <= 1.2:
                length_score = 1.0
            elif 0.8 <= length_ratio < 0.9 or 1.2 < length_ratio <= 1.3:
                length_score = 0.8
            else:
                length_score = 0.6

            scores.append(length_score)

        return np.mean(scores) if scores else 1.0

    def _check_sentence_completeness(
        self,
        chunks: list[dict[str, Any]],
    ) -> float:
        """
        检查句子完整性

        Args:
            chunks: 分块列表

        Returns:
            完整性分数
        """
        incomplete_count = 0

        for chunk in chunks:
            content = chunk["content"].strip()

            if not content:
                incomplete_count += 1
                continue

            # 检查是否以句子结束符结尾
            if not self._ends_with_sentence_boundary(content):
                incomplete_count += 1

        # 完整率
        completeness_rate = 1 - (incomplete_count / len(chunks))

        return completeness_rate

    def _ends_with_sentence_boundary(self, text: str) -> bool:
        """检查是否以句子边界结束"""
        sentence_endings = ["。", "！", "？", "；", ".", "!", "?", ";"]
        return any(text.endswith(ending) for ending in sentence_endings)

    def _evaluate_coherence(
        self,
        chunks: list[dict[str, Any]],
    ) -> float:
        """
        评估连贯性（chunk之间的逻辑连贯性）

        策略:
        1. 检查相邻chunks的相似度
        2. 检查上下文连续性

        Args:
            chunks: 分块列表

        Returns:
            连贯性分数 (0-1)
        """
        if len(chunks) <= 1:
            return 1.0

        # 简单实现：检查相邻chunks的首尾连接
        coherence_scores = []

        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]["content"]
            next_chunk = chunks[i + 1]["content"]

            # 提取尾部和头部的词
            current_end_words = self._extract_words(current_chunk, position="end", n=5)
            next_start_words = self._extract_words(next_chunk, position="start", n=5)

            # 计算重叠度
            overlap = len(set(current_end_words) & set(next_start_words))
            coherence_score = min(overlap / 5.0, 1.0)  # 归一化到0-1

            coherence_scores.append(coherence_score)

        return np.mean(coherence_scores)

    def _extract_words(
        self,
        text: str,
        position: str = "start",
        n: int = 5,
    ) -> list[str]:
        """
        提取文本开头或结尾的词

        Args:
            text: 文本
            position: 'start' 或 'end'
            n: 词数

        Returns:
            词列表
        """
        # 简单分词（按空格和标点）
        words = re.findall(r'\w+', text)

        if position == "start":
            return words[:n]
        else:
            return words[-n:] if len(words) >= n else words

    def _evaluate_size(
        self,
        chunks: list[dict[str, Any]],
    ) -> float:
        """
        评估大小合理性

        策略:
        1. 检查大小分布是否均匀
        2. 检查是否有异常大小的chunk

        Args:
            chunks: 分块列表

        Returns:
            大小合理性分数 (0-1)
        """
        sizes = [len(c["content"]) for c in chunks]

        if not sizes:
            return 0.0

        mean_size = np.mean(sizes)
        std_size = np.std(sizes)

        # 计算变异系数 (CV)
        cv = std_size / mean_size if mean_size > 0 else 0

        # CV越小越好（表示大小越均匀）
        # CV < 0.3: excellent
        # CV < 0.5: good
        # CV < 0.7: acceptable
        # CV >= 0.7: poor

        if cv < 0.3:
            size_score = 1.0
        elif cv < 0.5:
            size_score = 0.9
        elif cv < 0.7:
            size_score = 0.7
        else:
            size_score = 0.5

        return size_score

    def _evaluate_overlap(
        self,
        chunks: list[dict[str, Any]],
    ) -> float:
        """
        评估重叠度

        Args:
            chunks: 分块列表

        Returns:
            重叠度分数 (0-1)
        """
        if len(chunks) <= 1:
            return 1.0

        overlap_scores = []

        for i in range(len(chunks) - 1):
            current_content = chunks[i]["content"]
            next_content = chunks[i + 1]["content"]

            # 查找重叠部分
            overlap_length = self._find_overlap_length(current_content, next_content)
            overlap_ratio = overlap_length / min(len(current_content), len(next_content))

            # 理想的重叠比例：5-15%
            if 0.05 <= overlap_ratio <= 0.15:
                score = 1.0
            elif 0.0 <= overlap_ratio < 0.05 or 0.15 < overlap_ratio <= 0.25:
                score = 0.8
            else:
                score = 0.6

            overlap_scores.append(score)

        return np.mean(overlap_scores)

    def _find_overlap_length(self, text1: str, text2: str) -> int:
        """
        查找两个文本的重叠长度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            重叠字符数
        """
        # 简单实现：查找text1的尾部和text2的头部的最长公共子串
        max_overlap = 0

        for i in range(1, min(len(text1), len(text2)) + 1):
            if text1[-i:] == text2[:i]:
                max_overlap = i

        return max_overlap

    def _generate_recommendations(
        self,
        completeness_score: float,
        coherence_score: float,
        size_score: float,
        overlap_score: float,
    ) -> list[str]:
        """
        生成优化建议

        Args:
            completeness_score: 完整性分数
            coherence_score: 连贯性分数
            size_score: 大小分数
            overlap_score: 重叠分数

        Returns:
            建议列表
        """
        recommendations = []

        if completeness_score < 0.9:
            recommendations.append(
                "Improve completeness: Consider using semantic chunking to preserve sentence boundaries"
            )

        if coherence_score < 0.8:
            recommendations.append(
                "Improve coherence: Increase overlap between chunks to maintain context"
            )

        if size_score < 0.7:
            recommendations.append(
                "Improve size distribution: Use adaptive chunking strategies to balance chunk sizes"
            )

        if overlap_score < 0.6:
            recommendations.append(
                "Optimize overlap: Adjust overlap parameter to 5-15% of chunk size"
            )

        if not recommendations:
            recommendations.append("Quality is good. No improvements needed.")

        return recommendations


class ComparativeEvaluator:
    """对比评估器（对比不同分块策略）"""

    def __init__(self, evaluator: ChunkQualityEvaluator):
        """
        初始化对比评估器

        Args:
            evaluator: 质量评估器
        """
        self.evaluator = evaluator

    async def compare_strategies(
        self,
        strategies_results: dict[str, list[dict[str, Any]]],
        original_text: str | None = None,
    ) -> dict[str, Any]:
        """
        对比不同分块策略的效果

        Args:
            strategies_results: 策略名称 -> 分块结果的映射
            original_text: 原始文本

        Returns:
            对比结果
        """
        results = {}

        for strategy_name, chunks in strategies_results.items():
            evaluation = await self.evaluator.evaluate(chunks, original_text)
            results[strategy_name] = evaluation

        # 排序（按总分）
        ranked_strategies = sorted(
            results.items(),
            key=lambda x: x[1]["overall_score"],
            reverse=True,
        )

        comparison = {
            "strategies": results,
            "ranking": [name for name, _ in ranked_strategies],
            "best_strategy": ranked_strategies[0][0] if ranked_strategies else None,
            "best_score": ranked_strategies[0][1]["overall_score"] if ranked_strategies else 0.0,
        }

        logger.info(
            f"Strategy comparison: best={comparison['best_strategy']} "
            f"(score={comparison['best_score']:.2f})"
        )

        return comparison

    def generate_report(
        self,
        comparison: dict[str, Any],
    ) -> str:
        """
        生成评估报告

        Args:
            comparison: 对比结果

        Returns:
            报告文本
        """
        report_lines = [
            "# Chunking Strategy Evaluation Report",
            "",
            f"**Best Strategy**: {comparison['best_strategy']} (Score: {comparison['best_score']:.2f})",
            "",
            "## Strategy Rankings",
            "",
        ]

        for rank, strategy_name in enumerate(comparison["ranking"], 1):
            strategy_result = comparison["strategies"][strategy_name]
            report_lines.append(f"{rank}. **{strategy_name}**")
            report_lines.append(f"   - Overall Score: {strategy_result['overall_score']:.2f}")
            report_lines.append(f"   - Completeness: {strategy_result['scores']['completeness']:.2f}")
            report_lines.append(f"   - Coherence: {strategy_result['scores']['coherence']:.2f}")
            report_lines.append(f"   - Size: {strategy_result['scores']['size']:.2f}")
            report_lines.append(f"   - Overlap: {strategy_result['scores']['overlap']:.2f}")
            report_lines.append("")

        report_lines.append("## Detailed Analysis")
        report_lines.append("")

        for strategy_name, strategy_result in comparison["strategies"].items():
            report_lines.append(f"### {strategy_name}")
            report_lines.append("")

            stats = strategy_result["statistics"]
            report_lines.append(f"- Total Chunks: {stats['total_chunks']}")
            report_lines.append(f"- Avg Chunk Size: {stats['avg_chunk_size']:.0f} chars")
            report_lines.append(f"- Size Std Dev: {stats['std_chunk_size']:.0f}")
            report_lines.append(f"- Min/Max Size: {stats['min_chunk_size']}/{stats['max_chunk_size']}")
            report_lines.append("")

            if strategy_result["issues"]:
                report_lines.append("**Issues:**")
                for issue in strategy_result["issues"]:
                    report_lines.append(f"- {issue}")
                report_lines.append("")

            if strategy_result["recommendations"]:
                report_lines.append("**Recommendations:**")
                for rec in strategy_result["recommendations"]:
                    report_lines.append(f"- {rec}")
                report_lines.append("")

        return "\n".join(report_lines)
