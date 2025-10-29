"""
Context Compressor - 上下文压缩器

使用 LLMLingua 或规则方法压缩上下文，节省 Token
"""

import logging
import re

logger = logging.getLogger(__name__)


class ContextCompressor:
    """上下文压缩器"""

    def __init__(
        self,
        use_llmlingua: bool = False,
        llmlingua_model: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
    ):
        """
        初始化上下文压缩器

        Args:
            use_llmlingua: 使用 LLMLingua 模型
            llmlingua_model: LLMLingua 模型名称
        """
        self.use_llmlingua = use_llmlingua

        if use_llmlingua:
            try:
                from llmlingua import PromptCompressor

                self.compressor = PromptCompressor(model_name=llmlingua_model)
                logger.info(f"LLMLingua compressor initialized: {llmlingua_model}")
            except Exception as e:
                logger.warning(f"Failed to load LLMLingua: {e}, falling back to rule-based")
                self.use_llmlingua = False

        if not use_llmlingua:
            logger.info("Context compressor initialized with rule-based method")

    def compress(
        self,
        context: str,
        query: str,
        compression_ratio: float = 0.5,
        preserve_entities: bool = True,
        preserve_numbers: bool = True,
    ) -> dict[str, any]:
        """
        压缩上下文

        Args:
            context: 原始上下文
            query: 查询（用于相关性判断）
            compression_ratio: 压缩比例（0.3-0.7）
            preserve_entities: 保留实体
            preserve_numbers: 保留数字

        Returns:
            压缩结果
        """
        original_length = len(context)

        if self.use_llmlingua:
            compressed_result = self._compress_with_llmlingua(context, query, compression_ratio)
        else:
            compressed_result = self._compress_with_rules(
                context, query, compression_ratio, preserve_entities, preserve_numbers
            )

        compressed_context = compressed_result["compressed_context"]
        compressed_length = len(compressed_context)
        actual_ratio = compressed_length / max(original_length, 1)

        logger.info(
            f"Context compressed: {original_length} -> {compressed_length} chars "
            f"(ratio: {actual_ratio:.2f}, target: {compression_ratio:.2f})"
        )

        return {
            "compressed_context": compressed_context,
            "original_length": original_length,
            "compressed_length": compressed_length,
            "compression_ratio": actual_ratio,
            "tokens_saved": (original_length - compressed_length) // 4,  # 估算
            "method": "llmlingua" if self.use_llmlingua else "rules",
            **compressed_result,
        }

    def _compress_with_llmlingua(
        self, context: str, query: str, compression_ratio: float
    ) -> dict[str, any]:
        """使用 LLMLingua 压缩"""
        try:
            result = self.compressor.compress_prompt(
                context=context,
                instruction=query,
                rate=compression_ratio,
                target_token=-1,  # 自动计算
            )

            return {
                "compressed_context": result["compressed_prompt"],
                "origin_tokens": result.get("origin_tokens", 0),
                "compressed_tokens": result.get("compressed_tokens", 0),
            }
        except Exception as e:
            logger.error(f"LLMLingua compression failed: {e}")
            # 回退到规则方法
            return self._compress_with_rules(context, query, compression_ratio, True, True)

    def _compress_with_rules(
        self,
        context: str,
        query: str,
        compression_ratio: float,
        preserve_entities: bool,
        preserve_numbers: bool,
    ) -> dict[str, any]:
        """使用规则压缩（回退方案）"""
        # 策略 1: 按句子重要性排序，保留前 N 句
        sentences = self._split_sentences(context)

        # 计算每句的重要性分数
        scored_sentences = []
        query_words = set(query.lower().split())

        for i, sentence in enumerate(sentences):
            score = self._calculate_sentence_score(
                sentence, query_words, i, len(sentences), preserve_entities, preserve_numbers
            )
            scored_sentences.append({"sentence": sentence, "score": score, "position": i})

        # 按分数排序
        scored_sentences.sort(key=lambda x: x["score"], reverse=True)

        # 选择句子直到达到压缩比例
        target_length = int(len(context) * compression_ratio)
        selected_sentences = []
        current_length = 0

        for item in scored_sentences:
            sentence = item["sentence"]
            if current_length + len(sentence) <= target_length or not selected_sentences:
                selected_sentences.append(item)
                current_length += len(sentence)

        # 按原始顺序排列
        selected_sentences.sort(key=lambda x: x["position"])

        # 组合句子
        compressed_context = " ".join([item["sentence"] for item in selected_sentences])

        return {
            "compressed_context": compressed_context,
            "selected_sentences": len(selected_sentences),
            "total_sentences": len(sentences),
        }

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        sentences = re.split(r"[。！？.!?]\s*", text)
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_sentence_score(
        self,
        sentence: str,
        query_words: set,
        position: int,
        total_sentences: int,
        preserve_entities: bool,
        preserve_numbers: bool,
    ) -> float:
        """计算句子重要性分数"""
        score = 0.0

        sentence_lower = sentence.lower()
        sentence_words = set(sentence_lower.split())

        # 1. 与查询的重叠度（最重要）
        overlap = len(query_words & sentence_words)
        score += overlap * 3.0

        # 2. 位置权重（开头和结尾更重要）
        if position < 3:
            score += 2.0  # 开头
        elif position >= total_sentences - 3:
            score += 1.5  # 结尾

        # 3. 句子长度（适中的句子更可能包含重要信息）
        length_score = min(len(sentence) / 100, 1.0)
        score += length_score

        # 4. 包含实体（大写词）
        if preserve_entities:
            entity_count = len(re.findall(r"\b[A-Z][a-z]+\b", sentence))
            score += entity_count * 0.5

        # 5. 包含数字
        if preserve_numbers:
            number_count = len(re.findall(r"\b\d+\.?\d*\b", sentence))
            score += number_count * 0.5

        # 6. 包含关键词
        keywords = ["重要", "关键", "核心", "主要", "首先", "总结", "因此", "所以"]
        keyword_count = sum(1 for kw in keywords if kw in sentence_lower)
        score += keyword_count * 1.0

        return score

    def compress_documents(
        self,
        documents: list[dict[str, any]],
        query: str,
        compression_ratio: float = 0.5,
    ) -> list[dict[str, any]]:
        """
        压缩文档列表

        Args:
            documents: 文档列表
            query: 查询
            compression_ratio: 压缩比例

        Returns:
            压缩后的文档列表
        """
        compressed_docs = []

        for doc in documents:
            content = doc.get("content", "")
            if not content:
                compressed_docs.append(doc)
                continue

            # 压缩内容
            result = self.compress(
                context=content,
                query=query,
                compression_ratio=compression_ratio,
            )

            # 创建压缩后的文档
            compressed_doc = doc.copy()
            compressed_doc["content"] = result["compressed_context"]
            compressed_doc["original_content"] = content
            compressed_doc["compression_info"] = {
                "original_length": result["original_length"],
                "compressed_length": result["compressed_length"],
                "compression_ratio": result["compression_ratio"],
                "tokens_saved": result["tokens_saved"],
            }

            compressed_docs.append(compressed_doc)

        total_tokens_saved = sum(
            doc.get("compression_info", {}).get("tokens_saved", 0) for doc in compressed_docs
        )

        logger.info(f"Compressed {len(documents)} documents, saved ~{total_tokens_saved} tokens")

        return compressed_docs

    def smart_compress(
        self,
        context: str,
        query: str,
        max_tokens: int = 2000,
        preserve_entities: bool = True,
        preserve_numbers: bool = True,
    ) -> dict[str, any]:
        """
        智能压缩：根据目标 token 数自动调整压缩比例

        Args:
            context: 上下文
            query: 查询
            max_tokens: 最大 token 数
            preserve_entities: 保留实体
            preserve_numbers: 保留数字

        Returns:
            压缩结果
        """
        # 估算当前 token 数（1 token ≈ 4 chars）
        current_tokens = len(context) // 4

        if current_tokens <= max_tokens:
            # 不需要压缩
            return {
                "compressed_context": context,
                "original_length": len(context),
                "compressed_length": len(context),
                "compression_ratio": 1.0,
                "tokens_saved": 0,
                "method": "no_compression",
            }

        # 计算需要的压缩比例
        target_compression_ratio = max_tokens / current_tokens
        target_compression_ratio = max(0.3, min(0.8, target_compression_ratio))  # 限制范围

        logger.info(
            f"Smart compress: {current_tokens} -> {max_tokens} tokens "
            f"(ratio: {target_compression_ratio:.2f})"
        )

        return self.compress(
            context=context,
            query=query,
            compression_ratio=target_compression_ratio,
            preserve_entities=preserve_entities,
            preserve_numbers=preserve_numbers,
        )
