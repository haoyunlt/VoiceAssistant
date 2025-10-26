import io
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


class OCREngine:
    """
    OCR 引擎，支持多种 OCR 提供商。
    """

    def __init__(self):
        self.provider = os.getenv("OCR_PROVIDER", "paddleocr")  # paddleocr, azure, google
        self.api_key = os.getenv("OCR_API_KEY", "")
        self.endpoint = os.getenv("OCR_ENDPOINT", "")

        self.stats = {
            "total_ocr_requests": 0,
            "successful_ocr_requests": 0,
            "failed_ocr_requests": 0,
        }

        logger.info(f"OCREngine initialized with provider: {self.provider}")

    async def initialize(self):
        """初始化 OCR 引擎"""
        logger.info("Initializing OCR Engine...")

        if self.provider == "paddleocr":
            # PaddleOCR 不需要额外初始化
            pass
        elif self.provider == "azure":
            # Azure Computer Vision OCR
            if not self.api_key or not self.endpoint:
                logger.warning("Azure OCR credentials not configured")
        elif self.provider == "google":
            # Google Cloud Vision API
            if not self.api_key:
                logger.warning("Google Cloud Vision API key not configured")

        logger.info("OCR Engine initialized.")

    async def recognize(
        self,
        image_data: bytes,
        language: str = "auto",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        识别图片中的文字。

        Args:
            image_data: 图片二进制数据
            language: 语言代码 (auto, en, zh, etc.)
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "text": "完整文本",
                "confidence": 0.95,
                "regions": [
                    {
                        "text": "区域文本",
                        "bbox": [x, y, w, h],
                        "confidence": 0.9
                    },
                    ...
                ]
            }
        """
        self.stats["total_ocr_requests"] += 1

        try:
            if self.provider == "paddleocr":
                result = await self._recognize_paddleocr(image_data, language)
            elif self.provider == "azure":
                result = await self._recognize_azure(image_data, language)
            elif self.provider == "google":
                result = await self._recognize_google(image_data, language)
            else:
                raise ValueError(f"Unsupported OCR provider: {self.provider}")

            self.stats["successful_ocr_requests"] += 1
            return result

        except Exception as e:
            self.stats["failed_ocr_requests"] += 1
            logger.error(f"OCR recognition failed: {e}", exc_info=True)
            raise

    async def _recognize_paddleocr(
        self, image_data: bytes, language: str
    ) -> Dict[str, Any]:
        """使用 PaddleOCR 识别（模拟实现）"""
        logger.debug("Using PaddleOCR for text recognition")

        # 这里是模拟实现，实际需要安装 paddleocr 包
        # from paddleocr import PaddleOCR
        # ocr = PaddleOCR(use_angle_cls=True, lang='ch')
        # result = ocr.ocr(image_data)

        # 模拟返回结果
        return {
            "text": "Sample OCR text from PaddleOCR",
            "confidence": 0.92,
            "regions": [
                {
                    "text": "Sample text region 1",
                    "bbox": [10, 10, 100, 30],
                    "confidence": 0.95,
                },
                {
                    "text": "Sample text region 2",
                    "bbox": [10, 50, 120, 70],
                    "confidence": 0.89,
                },
            ],
            "provider": "paddleocr",
        }

    async def _recognize_azure(
        self, image_data: bytes, language: str
    ) -> Dict[str, Any]:
        """使用 Azure Computer Vision OCR"""
        logger.debug("Using Azure Computer Vision for text recognition")

        if not self.api_key or not self.endpoint:
            raise ValueError("Azure OCR credentials not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/octet-stream",
            }

            url = f"{self.endpoint}/vision/v3.2/ocr"
            params = {"language": language if language != "auto" else "unk"}

            response = await client.post(
                url, headers=headers, params=params, content=image_data
            )
            response.raise_for_status()

            data = response.json()

            # 解析 Azure 响应
            regions = []
            full_text = []

            for region in data.get("regions", []):
                for line in region.get("lines", []):
                    line_text = " ".join([word["text"] for word in line.get("words", [])])
                    full_text.append(line_text)

                    bbox = line.get("boundingBox", "0,0,0,0").split(",")
                    regions.append({
                        "text": line_text,
                        "bbox": [int(x) for x in bbox],
                        "confidence": 0.9,  # Azure 不提供置信度
                    })

            return {
                "text": "\n".join(full_text),
                "confidence": 0.9,
                "regions": regions,
                "provider": "azure",
            }

    async def _recognize_google(
        self, image_data: bytes, language: str
    ) -> Dict[str, Any]:
        """使用 Google Cloud Vision API（模拟实现）"""
        logger.debug("Using Google Cloud Vision for text recognition")

        # 模拟实现
        return {
            "text": "Sample OCR text from Google Cloud Vision",
            "confidence": 0.94,
            "regions": [
                {
                    "text": "Sample text from Google",
                    "bbox": [15, 15, 110, 35],
                    "confidence": 0.96,
                },
            ],
            "provider": "google",
        }

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats

    async def is_ready(self) -> bool:
        """检查是否准备就绪"""
        return True

    async def cleanup(self):
        """清理资源"""
        logger.info("OCR Engine cleaned up.")
