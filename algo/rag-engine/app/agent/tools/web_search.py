"""
网络搜索工具 - Web Search Tool

使用 SerpAPI 进行实时网络搜索，获取最新信息。
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class WebSearchTool:
    """网络搜索工具"""

    def __init__(self, api_key: str | None = None):
        """
        初始化网络搜索工具

        Args:
            api_key: SerpAPI API Key（可选，优先使用环境变量 SERPAPI_API_KEY）
        """
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        self.name = "web_search"
        self.description = "在互联网上搜索最新信息，适用于实时数据、新闻、天气等动态内容"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量（默认5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行网络搜索

        Args:
            params: 包含 query, num_results

        Returns:
            {
                "text": "搜索结果文本描述",
                "results": [...],
                "count": 5
            }
        """
        query = params.get("query")
        num_results = params.get("num_results", 5)

        if not query:
            raise ValueError("query 参数不能为空")

        logger.info(f"Web search: query={query[:50]}, num_results={num_results}")

        # 检查 API Key
        if not self.api_key:
            logger.warning("SERPAPI_API_KEY not set, using mock results")
            return self._mock_search(query, num_results)

        try:
            # 使用 SerpAPI
            results = await self._serpapi_search(query, num_results)

            # 构建文本描述
            text = self._format_results(results) if results else "未找到相关结果"

            return {
                "text": text,
                "results": results,
                "count": len(results),
            }

        except Exception as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return {
                "text": f"网络搜索失败：{str(e)}",
                "results": [],
                "count": 0,
                "error": str(e),
            }

    async def _serpapi_search(self, query: str, num_results: int) -> list[dict[str, Any]]:
        """使用 SerpAPI 进行搜索"""
        try:
            import httpx

            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "engine": "google",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # 提取有机搜索结果
                organic_results = data.get("organic_results", [])

                results = []
                for item in organic_results[:num_results]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "link": item.get("link", ""),
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            raise

    def _mock_search(self, query: str, num_results: int) -> dict[str, Any]:
        """模拟搜索（用于测试）"""
        mock_results = [
            {
                "title": f"关于 {query} 的搜索结果 1",
                "snippet": f"这是一个模拟的搜索结果，包含 {query} 的相关信息...",
                "link": f"https://example.com/result1?q={query}",
            },
            {
                "title": f"关于 {query} 的搜索结果 2",
                "snippet": f"另一个关于 {query} 的信息来源...",
                "link": f"https://example.com/result2?q={query}",
            },
        ]

        results = mock_results[:num_results]

        return {
            "text": self._format_results(results)
            + "\n\n⚠️ 注意：这是模拟结果（未配置 SERPAPI_API_KEY）",
            "results": results,
            "count": len(results),
        }

    def _format_results(self, results: list) -> str:
        """格式化搜索结果为文本"""
        if not results:
            return "未找到相关结果"

        text_parts = [f"找到 {len(results)} 个搜索结果：\n"]

        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")[:150]  # 截断

            text_parts.append(f"{i}. {title}\n   {snippet}...")

        return "\n\n".join(text_parts)
