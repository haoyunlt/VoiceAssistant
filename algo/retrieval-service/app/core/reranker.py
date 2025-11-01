"""重排序器 - Cross-Encoder"""

import logging

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-Encoder 重排序器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        初始化重排序器

        Args:
            model_name: Cross-Encoder 模型名称
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"Reranker created with model: {model_name}")

    async def initialize(self):
        """初始化模型"""
        logger.info(f"Loading reranker model: {self.model_name}...")

        # 加载 Cross-Encoder 模型
        self.model = CrossEncoder(self.model_name)

        logger.info("Reranker model loaded successfully")

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回结果数

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        # 提取文档内容
        doc_contents = [doc.get("content", "") for doc in documents]

        # 构建查询-文档对
        query_doc_pairs = [[query, doc] for doc in doc_contents]

        # 计算相关性分数
        scores = self.model.predict(query_doc_pairs)

        # 将分数添加到文档
        for doc, score in zip(documents, scores, strict=False):
            doc["rerank_score"] = float(score)

        # 按分数排序
        reranked = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)

        # 取 Top K
        top_results = reranked[:top_k]

        logger.info(f"Reranked {len(documents)} → {len(top_results)} documents")

        return top_results


class LLMReranker:
    """基于 LLM 的重排序器（可选）"""

    def __init__(self, llm_endpoint: str | None = None, model: str = "qwen-7b"):
        """初始化 LLM 重排序器"""
        self.llm_endpoint = llm_endpoint
        self.model = model
        self.llm_client = None
        logger.info(f"LLM reranker created: endpoint={llm_endpoint}, model={model}")

    async def initialize(self):
        """初始化 LLM 客户端"""
        if not self.llm_endpoint:
            logger.warning("No LLM endpoint configured for reranking")
            return

        try:
            import sys
            from pathlib import Path

            # 添加 common 路径
            common_path = Path(__file__).parent.parent.parent.parent.parent / "common"
            if str(common_path) not in sys.path:
                sys.path.insert(0, str(common_path))

            from llm_client import LLMClient

            self.llm_client = LLMClient(base_url=self.llm_endpoint, model=self.model)
            logger.info("LLM client initialized for reranking")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            self.llm_client = None

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        """
        使用 LLM 重排序文档

        通过 LLM 评估查询与文档的相关性
        策略：
        1. 为每个文档生成相关性评分（0-10）
        2. 按评分排序
        3. 返回 Top K
        """
        if not self.llm_client or not documents:
            logger.warning("LLM reranker unavailable or no documents, returning original order")
            return documents[:top_k]

        try:
            import asyncio

            async def score_document(doc: dict) -> tuple[dict, float]:
                """为单个文档评分"""
                content = doc.get("content", "")[:500]  # 限制长度

                prompt = f"""请评估以下文档与查询的相关性，给出0-10分（10分最相关）。

查询：{query}

文档：{content}

只返回数字分数，不要解释。"""

                try:
                    response = await self.llm_client.generate(
                        prompt=prompt, temperature=0.1, max_tokens=10
                    )

                    # 解析分数
                    score_text = response.strip()
                    score = float(score_text)
                    score = max(0.0, min(10.0, score))  # 限制在0-10

                    return doc, score
                except Exception as e:
                    logger.warning(f"Failed to score document: {e}")
                    return doc, 0.0

            # 并发评分（限制并发数避免过载）
            semaphore = asyncio.Semaphore(5)

            async def score_with_limit(doc):
                async with semaphore:
                    return await score_document(doc)

            tasks = [score_with_limit(doc) for doc in documents]
            scored_docs = await asyncio.gather(*tasks)

            # 按分数排序
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            # 添加 LLM 分数到文档
            reranked = []
            for doc, score in scored_docs[:top_k]:
                doc["llm_rerank_score"] = float(score)
                reranked.append(doc)

            logger.info(f"LLM reranked {len(documents)} → {len(reranked)} documents")
            return reranked

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}", exc_info=True)
            return documents[:top_k]
