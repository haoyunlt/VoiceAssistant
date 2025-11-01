"""生成服务"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeneratorService:
    """生成服务"""

    def __init__(self):
        self.model_adapter_url = settings.MODEL_ADAPTER_URL

    async def generate(
        self,
        query: str,
        context: str,
        history: list[dict[str, str]] = None,
        model: str = None,
        temperature: float = 0.7,
    ) -> str:
        """
        生成答案

        Args:
            query: 用户查询
            context: 上下文
            history: 对话历史
            model: LLM模型
            temperature: 温度参数

        Returns:
            生成的答案
        """
        try:
            # 构建提示词
            system_prompt = self._build_system_prompt(context)

            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]

            # 添加历史（如果有）
            if history:
                messages.extend(history[-5:])  # 只保留最近5轮对话

            # 添加当前查询
            messages.append({"role": "user", "content": query})

            # 调用模型适配器
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.model_adapter_url}/api/v1/chat/completions",
                    json={
                        "model": model or settings.DEFAULT_LLM_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": settings.LLM_MAX_TOKENS,
                    },
                )

                response.raise_for_status()
                data = response.json()

                answer = data["choices"][0]["message"]["content"]

                logger.info(f"Generated answer: {len(answer)} chars")
                return answer

        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            raise

    async def generate_stream(
        self,
        query: str,
        context: str,
        history: list[dict[str, str]] = None,
        model: str = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        流式生成答案

        Args:
            query: 用户查询
            context: 上下文
            history: 对话历史
            model: LLM模型
            temperature: 温度参数

        Yields:
            SSE格式的流式数据
        """
        try:
            # 构建提示词
            system_prompt = self._build_system_prompt(context)

            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]

            if history:
                messages.extend(history[-5:])

            messages.append({"role": "user", "content": query})

            # 调用模型适配器（流式）
            async with httpx.AsyncClient(timeout=120.0) as client:  # noqa: SIM117
                async with client.stream(
                    "POST",
                    f"{self.model_adapter_url}/api/v1/chat/completions",
                    json={
                        "model": model or settings.DEFAULT_LLM_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": settings.LLM_MAX_TOKENS,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break

                            # 转换格式
                            try:
                                chunk_data = json.loads(data)
                                content = (
                                    chunk_data.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )

                                if content:
                                    yield f"data: {json.dumps({'type': 'content', 'data': content})}\n\n"
                            except Exception:
                                pass

        except Exception as e:
            logger.error(f"Stream generation failed: {e}", exc_info=True)
            raise

    def _build_system_prompt(self, context: str) -> str:
        """构建系统提示词"""
        return f"""{settings.DEFAULT_SYSTEM_PROMPT}

Use the following context to answer the user's question. If the context doesn't contain relevant information, say so honestly.

Context:
{context}

Please provide a clear, accurate, and helpful answer based on the context above."""
