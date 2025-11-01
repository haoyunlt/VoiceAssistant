"""
向量检索工具 - Vector Search Tool

调用现有的检索服务进行向量搜索。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VectorSearchTool:
    """向量检索工具"""

    def __init__(self, retrieval_client):
        """
        初始化向量检索工具

        Args:
            retrieval_client: 检索服务客户端
        """
        self.retrieval_client = retrieval_client
        self.name = "vector_search"
        self.description = "在知识库中搜索相关文档，支持语义理解"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询文本",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回文档数量",
                    "default": 5,
                },
                "tenant_id": {
                    "type": "string",
                    "description": "租户ID",
                    "default": "default",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行向量检索

        Args:
            params: 包含 query, top_k, tenant_id

        Returns:
            {
                "text": "检索结果文本描述",
                "documents": [...],
                "count": 5
            }
        """
        query = params.get("query")
        top_k = params.get("top_k", 5)
        tenant_id = params.get("tenant_id", "default")

        if not query:
            raise ValueError("query 参数不能为空")

        logger.info(f"Vector search: query={query[:50]}, top_k={top_k}")

        try:
            # 调用检索服务
            result = await self.retrieval_client.search(
                query=query, top_k=top_k, tenant_id=tenant_id
            )

            documents = result.get("documents", [])

            # 构建文本描述
            if documents:
                text_parts = [f"找到 {len(documents)} 个相关文档：\n"]
                for i, doc in enumerate(documents[:3], 1):  # 只展示前3个
                    content = doc.get("content", "")[:200]  # 截断
                    score = doc.get("score", 0)
                    text_parts.append(f"{i}. (相关度: {score:.2f}) {content}...")

                if len(documents) > 3:
                    text_parts.append(f"\n... 还有 {len(documents) - 3} 个文档")

                text = "\n".join(text_parts)
            else:
                text = "未找到相关文档"

            return {
                "text": text,
                "documents": documents,
                "count": len(documents),
            }

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return {
                "text": f"检索失败：{str(e)}",
                "documents": [],
                "count": 0,
                "error": str(e),
            }
