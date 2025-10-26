"""检索服务客户端"""
import logging
from typing import List

import httpx

from app.core.config import settings
from app.models.rag import RetrievedDocument

logger = logging.getLogger(__name__)


class RetrievalClient:
    """检索服务客户端"""

    def __init__(self):
        self.retrieval_url = settings.RETRIEVAL_SERVICE_URL

    async def retrieve(
        self,
        queries: List[str],
        knowledge_base_id: str,
        tenant_id: str,
        top_k: int = 10,
    ) -> List[RetrievedDocument]:
        """
        调用检索服务

        Args:
            queries: 查询列表（支持多查询）
            knowledge_base_id: 知识库ID
            tenant_id: 租户ID
            top_k: 返回top-k结果

        Returns:
            检索到的文档列表
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 对每个查询进行检索
                all_documents = []

                for query in queries:
                    response = await client.post(
                        f"{self.retrieval_url}/api/v1/search",
                        json={
                            "query": query,
                            "knowledge_base_id": knowledge_base_id,
                            "tenant_id": tenant_id,
                            "top_k": top_k,
                        },
                    )

                    response.raise_for_status()
                    data = response.json()

                    # 解析检索结果
                    for item in data.get("results", []):
                        doc = RetrievedDocument(
                            chunk_id=item.get("chunk_id", ""),
                            document_id=item.get("document_id", ""),
                            content=item.get("content", ""),
                            score=item.get("score", 0.0),
                            metadata=item.get("metadata", {}),
                        )
                        all_documents.append(doc)

                # 去重和排序
                unique_docs = self._deduplicate_documents(all_documents)
                sorted_docs = sorted(unique_docs, key=lambda x: x.score, reverse=True)

                return sorted_docs[:top_k]

        except httpx.HTTPError as e:
            logger.error(f"Retrieval service request failed: {e}")
            # 返回空列表而不是抛出异常
            return []
        except Exception as e:
            logger.error(f"Retrieval failed: {e}", exc_info=True)
            return []

    def _deduplicate_documents(
        self, documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """去重文档"""
        seen_ids = set()
        unique_docs = []

        for doc in documents:
            if doc.chunk_id not in seen_ids:
                seen_ids.add(doc.chunk_id)
                unique_docs.append(doc)

        return unique_docs
