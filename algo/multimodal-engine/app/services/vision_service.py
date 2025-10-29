"""
Vision understanding service (using Vision LLMs)
"""

import base64
import logging
import time

import httpx

from app.core.config import settings
from app.models.multimodal import VisionRequest, VisionResponse

logger = logging.getLogger(__name__)


class VisionService:
    """视觉理解服务（使用 Vision LLM）"""

    def __init__(self):
        self.provider = settings.VISION_PROVIDER
        self.model_adapter_endpoint = settings.MODEL_ADAPTER_ENDPOINT

    async def understand(self, request: VisionRequest) -> VisionResponse:
        """
        视觉理解

        Args:
            request: Vision 请求

        Returns:
            Vision 响应
        """
        # 获取图像数据
        if request.image_base64:
            image_base64 = request.image_base64
        elif request.image_url:
            image_data = await self._download_image(request.image_url)
            image_base64 = base64.b64encode(image_data).decode("utf-8")
        else:
            raise ValueError("Either image_url or image_base64 must be provided")

        # 理解
        response = await self._understand_with_vision_llm(
            image_base64=image_base64,
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            detail=request.detail,
        )

        return response

    async def understand_from_bytes(
        self,
        image_data: bytes,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> VisionResponse:
        """
        从图像字节理解

        Args:
            image_data: 图像数据
            prompt: 问题或指令
            model: 模型名称
            max_tokens: 最大 Token 数

        Returns:
            Vision 响应
        """
        # 编码为 Base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # 理解
        response = await self._understand_with_vision_llm(
            image_base64=image_base64,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )

        return response

    async def _understand_with_vision_llm(
        self,
        image_base64: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        detail: str = "auto",
    ) -> VisionResponse:
        """使用 Vision LLM 理解图像"""
        start_time = time.time()

        try:
            model = model or settings.VISION_MODEL
            max_tokens = max_tokens or settings.VISION_MAX_TOKENS

            # 构建请求（OpenAI Vision API 格式）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": detail,
                            },
                        },
                    ],
                }
            ]

            # 调用 Model Adapter
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.model_adapter_endpoint}/api/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()

            # 提取回答
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens_used = result.get("usage", {}).get("total_tokens")

            processing_time_ms = (time.time() - start_time) * 1000

            return VisionResponse(
                answer=answer,
                model=model,
                tokens_used=tokens_used,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Vision LLM understanding failed: {e}", exc_info=True)
            raise

    async def _download_image(self, url: str) -> bytes:
        """下载图像文件"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            raise
