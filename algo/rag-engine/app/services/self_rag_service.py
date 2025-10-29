"""Self-RAG服务 - 自我反思的RAG系统"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SelfRAGService:
    """
    Self-RAG (Self-Reflective Retrieval Augmented Generation)

    核心特性：
    1. 检索质量评估：判断检索到的文档是否相关
    2. 生成质量评估：判断生成的答案质量
    3. 自我修正：基于评估结果调整策略
    4. 多轮迭代：支持多次检索和生成直到满意
    """

    def __init__(
        self,
        llm_client,
        retrieval_client,
        quality_threshold: float = 0.7,
        max_iterations: int = 3
    ):
        """
        初始化Self-RAG服务

        Args:
            llm_client: LLM客户端
            retrieval_client: 检索客户端
            quality_threshold: 质量阈值（0-1）
            max_iterations: 最大迭代次数
        """
        self.llm_client = llm_client
        self.retrieval_client = retrieval_client
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

    async def query(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: str | None = None
    ) -> dict[str, Any]:
        """
        执行Self-RAG查询

        Args:
            query: 用户查询
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID（可选）

        Returns:
            查询结果字典
        """
        logger.info(f"Starting Self-RAG query: {query}")

        iterations = []
        final_answer = None
        final_quality = 0.0

        for iteration in range(self.max_iterations):
            logger.info(f"Self-RAG iteration {iteration + 1}/{self.max_iterations}")

            # Step 1: 判断是否需要检索
            need_retrieval = await self._should_retrieve(query, iterations)

            iteration_data = {
                "iteration": iteration + 1,
                "need_retrieval": need_retrieval,
                "retrieval_quality": None,
                "retrieved_docs": [],
                "generated_answer": None,
                "answer_quality": None
            }

            if need_retrieval:
                # Step 2: 执行检索
                retrieved_docs = await self._retrieve_documents(
                    query=query,
                    tenant_id=tenant_id,
                    knowledge_base_id=knowledge_base_id
                )

                # Step 3: 评估检索质量
                retrieval_quality = await self._evaluate_retrieval(
                    query=query,
                    documents=retrieved_docs
                )

                iteration_data["retrieved_docs"] = retrieved_docs
                iteration_data["retrieval_quality"] = retrieval_quality

                logger.info(f"Retrieval quality: {retrieval_quality['score']:.2f}")

                # 如果检索质量太低，尝试重新formulate查询
                if retrieval_quality["score"] < self.quality_threshold:
                    logger.info("Retrieval quality low, reformulating query...")
                    reformulated_query = await self._reformulate_query(
                        original_query=query,
                        poor_results=retrieved_docs
                    )

                    # 使用重新formulate的查询再次检索
                    retrieved_docs = await self._retrieve_documents(
                        query=reformulated_query,
                        tenant_id=tenant_id,
                        knowledge_base_id=knowledge_base_id
                    )

                    # 重新评估
                    retrieval_quality = await self._evaluate_retrieval(
                        query=query,
                        documents=retrieved_docs
                    )

                    iteration_data["reformulated_query"] = reformulated_query
                    iteration_data["retrieved_docs"] = retrieved_docs
                    iteration_data["retrieval_quality"] = retrieval_quality

                # Step 4: 生成答案
                answer = await self._generate_answer(
                    query=query,
                    documents=retrieved_docs
                )

                iteration_data["generated_answer"] = answer
            else:
                # 直接生成答案（不需要检索）
                answer = await self._generate_answer_without_retrieval(query)
                iteration_data["generated_answer"] = answer

            # Step 5: 评估答案质量
            answer_quality = await self._evaluate_answer(
                query=query,
                answer=answer,
                documents=iteration_data.get("retrieved_docs", [])
            )

            iteration_data["answer_quality"] = answer_quality
            iterations.append(iteration_data)

            logger.info(f"Answer quality: {answer_quality['score']:.2f}")

            # Step 6: 判断是否达到质量标准
            if answer_quality["score"] >= self.quality_threshold:
                final_answer = answer
                final_quality = answer_quality["score"]
                logger.info(f"Quality threshold met in iteration {iteration + 1}")
                break

            # 如果这是最后一次迭代，使用当前答案
            if iteration == self.max_iterations - 1:
                final_answer = answer
                final_quality = answer_quality["score"]

        return {
            "answer": final_answer,
            "quality_score": final_quality,
            "iterations": len(iterations),
            "iteration_details": iterations,
            "metadata": {
                "query": query,
                "tenant_id": tenant_id,
                "knowledge_base_id": knowledge_base_id
            }
        }

    async def _should_retrieve(
        self,
        query: str,
        previous_iterations: list[dict]
    ) -> bool:
        """
        判断是否需要检索

        Args:
            query: 用户查询
            previous_iterations: 之前的迭代信息

        Returns:
            是否需要检索
        """
        # 使用LLM判断是否需要检索
        prompt = f"""Given the following query, determine if retrieval from a knowledge base is needed.

Query: {query}

Consider:
1. Is this a factual question that requires specific information?
2. Is this a general question that can be answered with common knowledge?
3. Would external documents help provide a better answer?

Respond with JSON:
{{
    "needs_retrieval": true/false,
    "reasoning": "brief explanation"
}}
"""

        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150
        )

        try:
            result = json.loads(response)
            return result.get("needs_retrieval", True)
        except json.JSONDecodeError:
            # 默认需要检索
            return True

    async def _retrieve_documents(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: str | None,
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """检索文档"""
        try:
            results = await self.retrieval_client.hybrid_search(
                query=query,
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                top_k=top_k
            )
            return results
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []

    async def _evaluate_retrieval(
        self,
        query: str,
        documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        评估检索质量

        Args:
            query: 查询
            documents: 检索到的文档

        Returns:
            评估结果
        """
        if not documents:
            return {
                "score": 0.0,
                "relevant_count": 0,
                "total_count": 0,
                "issues": ["No documents retrieved"]
            }

        # 构建评估prompt
        docs_text = "\n\n".join([
            f"[Doc {i+1}]: {doc.get('content', '')[:200]}..."
            for i, doc in enumerate(documents)
        ])

        prompt = f"""Evaluate the relevance of these retrieved documents to the query.

Query: {query}

Retrieved Documents:
{docs_text}

Rate each document's relevance (0-10) and provide an overall assessment.

Respond in JSON:
{{
    "overall_score": 0-10,
    "document_scores": [score1, score2, ...],
    "relevant_count": number,
    "issues": ["issue1", "issue2", ...]
}}
"""

        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=300
        )

        try:
            evaluation = json.loads(response)
            # 归一化分数到0-1
            score = evaluation.get("overall_score", 5) / 10.0
            return {
                "score": score,
                "relevant_count": evaluation.get("relevant_count", 0),
                "total_count": len(documents),
                "document_scores": evaluation.get("document_scores", []),
                "issues": evaluation.get("issues", [])
            }
        except json.JSONDecodeError:
            # 默认中等评分
            return {
                "score": 0.5,
                "relevant_count": len(documents) // 2,
                "total_count": len(documents),
                "issues": []
            }

    async def _reformulate_query(
        self,
        original_query: str,
        poor_results: list[dict[str, Any]]
    ) -> str:
        """重新formulate查询以获得更好的结果"""
        prompt = f"""The original query did not retrieve relevant documents. Reformulate the query to improve retrieval.

Original Query: {original_query}

Poor Results (first 2):
{json.dumps(poor_results[:2], indent=2)}

Generate a reformulated query that:
1. Adds more context or keywords
2. Uses different phrasing
3. Focuses on key concepts

Reformulated Query:"""

        reformulated = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )

        return reformulated.strip()

    async def _generate_answer(
        self,
        query: str,
        documents: list[dict[str, Any]]
    ) -> str:
        """基于检索到的文档生成答案"""
        context = "\n\n".join([
            f"[文档{i+1}]: {doc.get('content', '')}"
            for i, doc in enumerate(documents[:5])
        ])

        prompt = f"""Based on the following documents, answer the query.

Query: {query}

Documents:
{context}

Please provide a comprehensive answer based on the documents:"""

        answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=500
        )

        return answer.strip()

    async def _generate_answer_without_retrieval(self, query: str) -> str:
        """不使用检索直接生成答案"""
        prompt = f"""Answer the following query based on your knowledge:

Query: {query}

Answer:"""

        answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=500
        )

        return answer.strip()

    async def _evaluate_answer(
        self,
        query: str,
        answer: str,
        documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        评估答案质量

        Args:
            query: 查询
            answer: 生成的答案
            documents: 使用的文档

        Returns:
            评估结果
        """
        prompt = f"""Evaluate the quality of this answer.

Query: {query}

Answer: {answer}

Evaluate on:
1. Relevance: Does it answer the query?
2. Accuracy: Is the information correct?
3. Completeness: Is it comprehensive enough?
4. Clarity: Is it well-written and clear?

Respond in JSON:
{{
    "overall_score": 0-10,
    "relevance": 0-10,
    "accuracy": 0-10,
    "completeness": 0-10,
    "clarity": 0-10,
    "strengths": ["strength1", ...],
    "weaknesses": ["weakness1", ...]
}}
"""

        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=400
        )

        try:
            evaluation = json.loads(response)
            # 归一化分数到0-1
            score = evaluation.get("overall_score", 5) / 10.0
            return {
                "score": score,
                "relevance": evaluation.get("relevance", 5) / 10.0,
                "accuracy": evaluation.get("accuracy", 5) / 10.0,
                "completeness": evaluation.get("completeness", 5) / 10.0,
                "clarity": evaluation.get("clarity", 5) / 10.0,
                "strengths": evaluation.get("strengths", []),
                "weaknesses": evaluation.get("weaknesses", [])
            }
        except json.JSONDecodeError:
            # 默认中等评分
            return {
                "score": 0.5,
                "relevance": 0.5,
                "accuracy": 0.5,
                "completeness": 0.5,
                "clarity": 0.5,
                "strengths": [],
                "weaknesses": []
            }
