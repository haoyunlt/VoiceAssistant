"""
真实工具实现

提供实际可用的工具，包括：
- 搜索工具 (SerpAPI)
- 知识库工具 (RAG Engine)
- 天气工具 (OpenWeather API)
- 计算器工具
"""

import ast
import operator as op
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SearchTool:
    """网络搜索工具 (基于 SerpAPI)"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化搜索工具

        Args:
            api_key: SerpAPI 密钥
        """
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.base_url = "https://serpapi.com/search"

    async def execute(self, query: str, num_results: int = 5) -> str:
        """
        执行搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量

        Returns:
            格式化的搜索结果
        """
        try:
            if not self.api_key:
                logger.warning("SERPAPI_KEY not configured, returning mock results")
                return self._mock_search(query)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "q": query,
                        "api_key": self.api_key,
                        "num": num_results,
                        "engine": "google",
                    },
                )

                if response.status_code != 200:
                    logger.error(f"Search API error: {response.status_code}")
                    return f"搜索失败: HTTP {response.status_code}"

                data = response.json()
                organic_results = data.get("organic_results", [])

                if not organic_results:
                    return "未找到相关结果"

                # 格式化结果
                results = []
                for i, result in enumerate(organic_results[:num_results], 1):
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")
                    link = result.get("link", "")
                    results.append(f"{i}. {title}\n   {snippet}\n   URL: {link}")

                return "\n\n".join(results)

        except httpx.TimeoutException:
            logger.error("Search API timeout")
            return "搜索超时，请稍后重试"
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return f"搜索出错: {str(e)}"

    def _mock_search(self, query: str) -> str:
        """模拟搜索结果（当 API key 未配置时）"""
        return f"""搜索结果 (模拟): "{query}"

1. {query} - 维基百科
   {query} 是指...这是一个模拟的搜索结果。
   URL: https://zh.wikipedia.org/wiki/{query}

2. {query} - 百度百科
   关于 {query} 的详细信息...
   URL: https://baike.baidu.com/item/{query}

注意: 这是模拟结果，请配置 SERPAPI_KEY 以获得真实搜索结果。"""

    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义（OpenAI Function Calling 格式）"""
        return {
            "name": "search",
            "description": "在互联网上搜索信息。当需要获取实时信息、最新新闻或不在知识库中的内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量（默认 5）",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        }


class KnowledgeBaseTool:
    """知识库查询工具"""

    def __init__(self, rag_service_url: Optional[str] = None):
        """
        初始化知识库工具

        Args:
            rag_service_url: RAG 服务 URL
        """
        self.rag_service_url = rag_service_url or os.getenv(
            "RAG_SERVICE_URL", "http://localhost:8006"
        )

    async def execute(
        self, query: str, knowledge_base_id: str = "default", top_k: int = 3
    ) -> str:
        """
        查询知识库

        Args:
            query: 查询问题
            knowledge_base_id: 知识库 ID
            top_k: 返回文档数量

        Returns:
            格式化的知识库结果
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.rag_service_url}/api/v1/rag/retrieve",
                    json={
                        "query": query,
                        "knowledge_base_id": knowledge_base_id,
                        "top_k": top_k,
                    },
                )

                if response.status_code != 200:
                    logger.error(f"RAG service error: {response.status_code}")
                    return self._mock_knowledge_search(query)

                data = response.json()
                documents = data.get("documents", [])

                if not documents:
                    return "知识库中未找到相关信息"

                # 格式化结果
                results = []
                for i, doc in enumerate(documents, 1):
                    content = doc.get("content", "")[:300]  # 截断长内容
                    metadata = doc.get("metadata", {})
                    source = metadata.get("title") or metadata.get("source", "未知来源")
                    score = doc.get("score", 0.0)

                    results.append(
                        f"{i}. {content}...\n"
                        f"   (来源: {source}, 相关度: {score:.2f})"
                    )

                return "\n\n".join(results)

        except httpx.ConnectError:
            logger.warning("RAG service not available, using mock results")
            return self._mock_knowledge_search(query)
        except Exception as e:
            logger.error(f"Knowledge base query failed: {e}", exc_info=True)
            return f"知识库查询失败: {str(e)}"

    def _mock_knowledge_search(self, query: str) -> str:
        """模拟知识库结果"""
        return f"""知识库结果 (模拟): "{query}"

1. 关于 {query} 的信息...
   这是一个模拟的知识库结果。实际使用时会从 RAG 服务检索真实文档。
   (来源: 知识库文档 #001, 相关度: 0.85)

2. {query} 的详细说明...
   更多相关内容...
   (来源: 知识库文档 #002, 相关度: 0.72)

注意: RAG 服务未连接，显示模拟结果。请确保 RAG Engine 正在运行。"""

    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "name": "knowledge_base",
            "description": "从企业知识库中检索信息。当需要查询公司文档、政策、产品信息时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询问题",
                    },
                    "knowledge_base_id": {
                        "type": "string",
                        "description": "知识库 ID（默认 default）",
                        "default": "default",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回文档数量（默认 3）",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        }


class WeatherTool:
    """天气查询工具"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化天气工具

        Args:
            api_key: OpenWeather API 密钥
        """
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    async def execute(self, city: str, country: str = "CN") -> str:
        """
        查询天气

        Args:
            city: 城市名称
            country: 国家代码（默认 CN）

        Returns:
            格式化的天气信息
        """
        try:
            if not self.api_key:
                logger.warning("OPENWEATHER_API_KEY not configured, returning mock weather")
                return self._mock_weather(city)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "q": f"{city},{country}",
                        "appid": self.api_key,
                        "units": "metric",  # 摄氏度
                        "lang": "zh_cn",
                    },
                )

                if response.status_code != 200:
                    logger.error(f"Weather API error: {response.status_code}")
                    return f"天气查询失败: HTTP {response.status_code}"

                data = response.json()

                # 提取天气信息
                weather_desc = data["weather"][0]["description"]
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                pressure = data["main"]["pressure"]

                return f"""{city} 当前天气:
- 天气状况: {weather_desc}
- 温度: {temp}°C (体感温度 {feels_like}°C)
- 湿度: {humidity}%
- 风速: {wind_speed} m/s
- 气压: {pressure} hPa"""

        except httpx.TimeoutException:
            logger.error("Weather API timeout")
            return "天气查询超时，请稍后重试"
        except KeyError as e:
            logger.error(f"Weather API response format error: {e}")
            return "天气数据格式错误"
        except Exception as e:
            logger.error(f"Weather query failed: {e}", exc_info=True)
            return f"天气查询出错: {str(e)}"

    def _mock_weather(self, city: str) -> str:
        """模拟天气结果"""
        return f"""{city} 当前天气 (模拟):
- 天气状况: 晴朗
- 温度: 25°C (体感温度 24°C)
- 湿度: 60%
- 风速: 3.5 m/s
- 气压: 1013 hPa

注意: 这是模拟结果，请配置 OPENWEATHER_API_KEY 以获得真实天气数据。"""

    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "name": "weather",
            "description": "查询指定城市的实时天气信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称（中文或英文），例如：北京、Beijing、上海、Shanghai",
                    },
                    "country": {
                        "type": "string",
                        "description": "国家代码（默认 CN，可选 US, JP 等）",
                        "default": "CN",
                    },
                },
                "required": ["city"],
            },
        }


class CalculatorTool:
    """计算器工具（安全的数学表达式求值）"""

    # 支持的运算符
    _operators = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.Mod: op.mod,
    }

    async def execute(self, expression: str) -> str:
        """
        执行计算

        Args:
            expression: 数学表达式，如 "2 + 3 * 4"

        Returns:
            计算结果
        """
        try:
            # 使用 AST 安全地求值
            result = self._eval_expr(expression)
            return f"{expression} = {result}"

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            return f"计算错误: {str(e)}"
        except Exception as e:
            logger.error(f"Calculator error: {e}", exc_info=True)
            return f"表达式无效: {str(e)}"

    def _eval_expr(self, expression: str) -> float:
        """
        安全地求值数学表达式

        Args:
            expression: 数学表达式

        Returns:
            计算结果

        Raises:
            ValueError: 不支持的表达式
        """
        try:
            node = ast.parse(expression, mode="eval")
            return self._eval_node(node.body)
        except SyntaxError:
            raise ValueError("语法错误")

    def _eval_node(self, node):
        """递归求值 AST 节点"""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            operator_func = self._operators.get(type(node.op))
            if operator_func is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return operator_func(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            operator_func = self._operators.get(type(node.op))
            if operator_func is None:
                raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
            return operator_func(operand)
        else:
            raise ValueError(f"不支持的表达式类型: {type(node).__name__}")

    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "name": "calculator",
            "description": "执行数学计算。支持加减乘除、幂运算和取模运算。例如: '2 + 3 * 4', '10 ** 2', '17 % 5'",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如: '2 + 3 * 4'、'(10 + 5) / 3'、'2 ** 8'",
                    }
                },
                "required": ["expression"],
            },
        }


class CurrentTimeTool:
    """当前时间工具"""

    async def execute(self, timezone: str = "Asia/Shanghai") -> str:
        """
        获取当前时间

        Args:
            timezone: 时区（默认 Asia/Shanghai）

        Returns:
            格式化的当前时间
        """
        try:
            now = datetime.now()
            return f"""当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
日期: {now.strftime('%Y年%m月%d日')}
星期: {['一', '二', '三', '四', '五', '六', '日'][now.weekday()]}
时区: {timezone}"""

        except Exception as e:
            logger.error(f"Time tool error: {e}", exc_info=True)
            return f"获取时间失败: {str(e)}"

    def get_definition(self) -> Dict[str, Any]:
        """获取工具定义"""
        return {
            "name": "current_time",
            "description": "获取当前日期和时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "时区（默认 Asia/Shanghai）",
                        "default": "Asia/Shanghai",
                    }
                },
                "required": [],
            },
        }


# 所有可用工具的列表
ALL_TOOLS = [
    SearchTool,
    KnowledgeBaseTool,
    WeatherTool,
    CalculatorTool,
    CurrentTimeTool,
]
