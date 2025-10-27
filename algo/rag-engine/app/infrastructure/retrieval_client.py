"""Retrieval Service客户端."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class RetrievalClient:
    """检索服务客户端."""

    def __init__(self, base_url: str = "http://retrieval-service:8012", timeout: int = 30):
        """
        初始化客户端.

        Args:
            base_url: Retrieval Service基础URL
            timeout: 请求超时时间(秒)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._closed = False

    async def __aenter__(self) -> "RetrievalClient":
        """异步上下文管理器入口."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器退出."""
        await self.close()

    async def close(self) -> None:
        """关闭客户端."""
        if not self._closed:
            await self.client.aclose()
            self._closed = True
            logger.debug("RetrievalClient closed")

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
        tenant_id: Optional[str] = None,
        rerank: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行检索.

        Args:
            query: 查询文本
            top_k: 返回结果数量
            mode: 检索模式 (vector/bm25/hybrid/graph)
            tenant_id: 租户ID (用于过滤)
            rerank: 是否重排序
            filters: 其他过滤条件

        Returns:
            检索结果列表，每个结果包含:
            - chunk_id: 分块ID
            - content: 文本内容
            - score: 相关性分数
            - metadata: 元数据 (document_id, filename等)
        """
        if self._closed:
            raise RuntimeError("RetrievalClient is closed")

        try:
            payload = {
                "query": query,
                "top_k": top_k,
                "mode": mode,
                "rerank": rerank,
            }

            if tenant_id:
                payload["tenant_id"] = tenant_id

            if filters:
                payload["filters"] = filters

            response = await self.client.post(
                f"{self.base_url}/retrieve", json=payload
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Retrieval HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise RuntimeError(
                f"Retrieval service error (HTTP {e.response.status_code}): {e.response.text[:200]}"
            )
        except httpx.TimeoutException as e:
            logger.error(f"Retrieval timeout: {e}")
            raise TimeoutError(f"Retrieval service timeout after {self.timeout}s")
        except httpx.HTTPError as e:
            logger.error(f"Retrieval request failed: {e}")
            raise RuntimeError(f"Failed to retrieve: {e}")

    async def multi_retrieve(
        self, queries: List[str], top_k: int = 10, **kwargs
    ) -> List[List[Dict[str, Any]]]:
        """
        批量检索.

        Args:
            queries: 查询文本列表
            top_k: 每个查询返回结果数量
            **kwargs: 其他参数传递给retrieve()

        Returns:
            每个查询的检索结果列表
        """
        results = []
        for query in queries:
            result = await self.retrieve(query, top_k=top_k, **kwargs)
            results.append(result)
        return results

    async def health_check(self) -> bool:
        """
        健康检查.

        Returns:
            服务是否健康
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
