import base64
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

try:
    from llm_client import UnifiedLLMClient
    USE_UNIFIED_CLIENT = True
except ImportError:
    USE_UNIFIED_CLIENT = False
    UnifiedLLMClient = None

logger = logging.getLogger(__name__)


class VisionEngine:
    """
    视觉理解引擎，支持图像理解和检测。
    """

    def __init__(self):
        self.provider = os.getenv("VISION_PROVIDER", "openai")  # openai, azure, anthropic
        self.api_key = os.getenv("VISION_API_KEY", "")
        self.endpoint = os.getenv("VISION_ENDPOINT", "https://api.openai.com/v1")
        self.model = os.getenv("VISION_MODEL", "gpt-4-vision-preview")

        # 优先使用统一LLM客户端
        if USE_UNIFIED_CLIENT:
            self.unified_client = UnifiedLLMClient(
                model_adapter_url=os.getenv("MODEL_ADAPTER_URL", "http://model-adapter:8005"),
                default_model=self.model,
                timeout=60,
            )
            logger.info("VisionEngine using UnifiedLLMClient (via model-adapter)")
        else:
            self.unified_client = None
            logger.warning("UnifiedLLMClient not available, using direct httpx client")

        self.client = httpx.AsyncClient(timeout=30.0)

        self.stats = {
            "total_vision_requests": 0,
            "successful_vision_requests": 0,
            "failed_vision_requests": 0,
        }

        logger.info(f"VisionEngine initialized with provider: {self.provider}")

    async def initialize(self):
        """初始化视觉引擎"""
        logger.info("Initializing Vision Engine...")
        logger.info("Vision Engine initialized.")

    async def understand(
        self,
        image_data: bytes,
        prompt: str = "Describe this image in detail.",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        图像理解（使用视觉语言模型）。

        Args:
            image_data: 图片二进制数据
            prompt: 提示词
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "description": "详细描述",
                "tags": ["tag1", "tag2"],
                "confidence": 0.92
            }
        """
        self.stats["total_vision_requests"] += 1

        try:
            if self.provider == "openai":
                result = await self._understand_openai(image_data, prompt)
            elif self.provider == "azure":
                result = await self._understand_azure(image_data, prompt)
            elif self.provider == "anthropic":
                result = await self._understand_anthropic(image_data, prompt)
            else:
                raise ValueError(f"Unsupported vision provider: {self.provider}")

            self.stats["successful_vision_requests"] += 1
            return result

        except Exception as e:
            self.stats["failed_vision_requests"] += 1
            logger.error(f"Vision understanding failed: {e}", exc_info=True)
            raise

    async def detect(
        self,
        image_data: bytes,
        detect_type: str = "objects",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        图像检测（对象、人脸、场景等）。

        Args:
            image_data: 图片二进制数据
            detect_type: 检测类型 (objects, faces, scenes, text)
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "detections": [
                    {"label": "person", "confidence": 0.95, "bbox": [x, y, w, h]},
                    ...
                ]
            }
        """
        self.stats["total_vision_requests"] += 1

        try:
            # 根据检测类型构造提示词
            if detect_type == "objects":
                prompt = "List all objects in this image with their locations."
            elif detect_type == "faces":
                prompt = "Detect all faces in this image and describe them."
            elif detect_type == "scenes":
                prompt = "Describe the scene and setting of this image."
            elif detect_type == "text":
                prompt = "Extract all visible text from this image."
            else:
                prompt = f"Detect {detect_type} in this image."

            # 使用理解接口进行检测
            result = await self.understand(image_data, prompt, tenant_id, user_id)

            # 转换为检测格式
            detection_result = {
                "detections": self._parse_detections(result["description"], detect_type),
                "raw_description": result["description"],
            }

            self.stats["successful_vision_requests"] += 1
            return detection_result

        except Exception as e:
            self.stats["failed_vision_requests"] += 1
            logger.error(f"Vision detection failed: {e}", exc_info=True)
            raise

    async def _understand_openai(
        self, image_data: bytes, prompt: str
    ) -> Dict[str, Any]:
        """使用 OpenAI GPT-4 Vision 理解图像"""
        logger.debug("Using OpenAI GPT-4 Vision for image understanding")

        # 将图片转换为 base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # 优先使用统一LLM客户端
        if self.unified_client:
            try:
                result = await self.unified_client.chat(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    },
                                },
                            ],
                        }
                    ],
                    model=self.model,
                    max_tokens=500,
                )
                description = result["content"]
            except Exception as e:
                logger.warning(f"UnifiedLLMClient failed, falling back to direct call: {e}")
                # 降级到直接调用
                description = await self._openai_direct_call(image_base64, prompt)
        else:
            # 直接调用OpenAI API
            description = await self._openai_direct_call(image_base64, prompt)

        # 提取标签（简单实现）
        tags = self._extract_tags(description)

        return {
            "description": description,
            "tags": tags,
            "confidence": 0.92,
            "provider": "openai",
            "model": self.model,
        }

    async def _openai_direct_call(self, image_base64: str, prompt: str) -> str:
        """直接调用OpenAI API（降级方案）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 500,
        }

        response = await self.client.post(
            f"{self.endpoint}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _understand_azure(
        self, image_data: bytes, prompt: str
    ) -> Dict[str, Any]:
        """使用 Azure Computer Vision（模拟实现）"""
        logger.debug("Using Azure Computer Vision for image understanding")

        # 模拟实现
        return {
            "description": "A sample image description from Azure Computer Vision.",
            "tags": ["sample", "azure", "vision"],
            "confidence": 0.89,
            "provider": "azure",
        }

    async def _understand_anthropic(
        self, image_data: bytes, prompt: str
    ) -> Dict[str, Any]:
        """使用 Anthropic Claude Vision（模拟实现）"""
        logger.debug("Using Anthropic Claude Vision for image understanding")

        # 模拟实现
        return {
            "description": "A sample image description from Claude Vision.",
            "tags": ["sample", "anthropic", "claude"],
            "confidence": 0.91,
            "provider": "anthropic",
        }

    def _extract_tags(self, description: str) -> List[str]:
        """从描述中提取标签（简单实现）"""
        # 这里可以使用 NLP 技术提取关键词
        # 简单实现：提取名词
        words = description.lower().split()
        common_objects = [
            "person", "car", "building", "tree", "sky", "water",
            "animal", "food", "furniture", "device", "book",
        ]
        tags = [word for word in words if word in common_objects]
        return list(set(tags))[:5]  # 返回最多 5 个标签

    def _parse_detections(
        self, description: str, detect_type: str
    ) -> List[Dict[str, Any]]:
        """从描述中解析检测结果（简单实现）"""
        # 这里应该使用更复杂的 NLP 技术解析
        # 简单实现：返回模拟数据
        if detect_type == "objects":
            return [
                {"label": "person", "confidence": 0.95, "bbox": [100, 100, 50, 100]},
                {"label": "car", "confidence": 0.88, "bbox": [300, 200, 80, 60]},
            ]
        elif detect_type == "faces":
            return [
                {"label": "face", "confidence": 0.97, "bbox": [120, 110, 40, 50]},
            ]
        else:
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats

    async def is_ready(self) -> bool:
        """检查是否准备就绪"""
        return True

    async def cleanup(self):
        """清理资源"""
        if self.client:
            await self.client.aclose()
        logger.info("Vision Engine cleaned up.")
