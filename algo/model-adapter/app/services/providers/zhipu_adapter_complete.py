"""
智谱 AI (GLM) 完整适配器实现
"""

import logging
import os
from collections.abc import AsyncIterator

import zhipuai
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)


class ZhipuAdapterComplete:
    """智谱 AI 完整适配器"""

    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            logger.warning("ZHIPU_API_KEY not configured")
            raise ValueError("ZHIPU_API_KEY not configured")

        zhipuai.api_key = self.api_key
        self.client = ZhipuAI(api_key=self.api_key)

    async def chat(self, request: dict) -> dict:
        """
        智谱 AI 聊天接口

        Args:
            request: 包含 model, messages, temperature 等的请求字典

        Returns:
            dict: 标准格式的响应
        """
        try:
            # 调用智谱 API
            response = self.client.chat.completions.create(
                model=request.get("model", "glm-4"),
                messages=request.get("messages", []),
                temperature=request.get("temperature", 0.95),
                top_p=request.get("top_p", 0.7),
                max_tokens=request.get("max_tokens", 2048),
                stream=False
            )

            # 转换为标准格式
            return {
                "id": response.id,
                "model": response.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response.choices[0].message.content
                        },
                        "finish_reason": response.choices[0].finish_reason
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except Exception as e:
            logger.error(f"Zhipu chat error: {e}")
            raise Exception(f"Zhipu API call failed: {str(e)}")

    async def chat_stream(self, request: dict) -> AsyncIterator[str]:
        """
        智谱 AI 流式聊天
        """
        try:
            # 流式调用
            response = self.client.chat.completions.create(
                model=request.get("model", "glm-4"),
                messages=request.get("messages", []),
                temperature=request.get("temperature", 0.95),
                max_tokens=request.get("max_tokens", 2048),
                stream=True
            )

            # 流式返回
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    import json
                    chunk_data = {
                        "id": chunk.id,
                        "object": "chat.completion.chunk",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk.choices[0].delta.content},
                                "finish_reason": chunk.choices[0].finish_reason
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"

        except Exception as e:
            logger.error(f"Zhipu stream error: {e}")
            raise Exception(f"Zhipu stream failed: {str(e)}")

    async def embedding(self, request: dict) -> dict:
        """
        智谱 AI Embedding

        Args:
            request: 包含 input 的请求字典

        Returns:
            dict: Embedding 响应
        """
        try:
            input_data = request.get("input", "")
            if isinstance(input_data, str):
                input_data = [input_data]

            # 调用智谱 Embedding API
            response = self.client.embeddings.create(
                model="embedding-2",
                input=input_data
            )

            return {
                "model": "embedding-2",
                "data": [
                    {
                        "embedding": item.embedding,
                        "index": item.index,
                        "object": "embedding"
                    }
                    for item in response.data
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except Exception as e:
            logger.error(f"Zhipu embedding error: {e}")
            raise Exception(f"Zhipu embedding failed: {str(e)}")
