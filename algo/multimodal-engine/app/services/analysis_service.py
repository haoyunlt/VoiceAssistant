"""
Image analysis service (综合分析)
"""

import base64
import io
import time
from typing import List

import httpx
from PIL import Image

from app.core.logging_config import get_logger
from app.models.multimodal import ImageAnalysisRequest, ImageAnalysisResponse
from app.services.ocr_service import OCRService
from app.services.vision_service import VisionService

logger = get_logger(__name__)


class AnalysisService:
    """图像综合分析服务"""

    def __init__(self):
        self.ocr_service = OCRService()
        self.vision_service = VisionService()

    async def analyze(self, request: ImageAnalysisRequest) -> ImageAnalysisResponse:
        """
        图像综合分析

        Args:
            request: 分析请求

        Returns:
            分析响应
        """
        # 获取图像数据
        if request.image_base64:
            image_data = base64.b64decode(request.image_base64)
        elif request.image_url:
            image_data = await self._download_image(request.image_url)
        else:
            raise ValueError("Either image_url or image_base64 must be provided")

        # 分析
        response = await self.analyze_from_bytes(
            image_data=image_data,
            tasks=request.tasks,
        )

        return response

    async def analyze_from_bytes(
        self,
        image_data: bytes,
        tasks: List[str],
    ) -> ImageAnalysisResponse:
        """
        从图像字节分析

        Args:
            image_data: 图像数据
            tasks: 分析任务列表

        Returns:
            分析响应
        """
        start_time = time.time()

        # 提取图像元数据
        metadata = self._extract_metadata(image_data)

        # 初始化结果
        description = None
        objects = None
        scene = None
        colors = None
        text = None

        # 执行各项任务
        for task in tasks:
            if task == "description":
                # 图像描述（使用 Vision LLM）
                description = await self._get_description(image_data)

            elif task == "objects":
                # 物体检测（使用 Vision LLM）
                objects = await self._detect_objects(image_data)

            elif task == "scene":
                # 场景识别（使用 Vision LLM）
                scene = await self._recognize_scene(image_data)

            elif task == "colors":
                # 主要颜色提取
                colors = self._extract_colors(image_data)

            elif task == "text":
                # OCR 文字识别
                ocr_result = await self.ocr_service.recognize_from_bytes(image_data)
                text = ocr_result.full_text

        processing_time_ms = (time.time() - start_time) * 1000

        return ImageAnalysisResponse(
            description=description,
            objects=objects,
            scene=scene,
            colors=colors,
            text=text,
            metadata=metadata,
            processing_time_ms=processing_time_ms,
        )

    async def _get_description(self, image_data: bytes) -> str:
        """获取图像描述"""
        try:
            result = await self.vision_service.understand_from_bytes(
                image_data=image_data,
                prompt="请详细描述这张图片的内容。",
                max_tokens=500,
            )
            return result.answer
        except Exception as e:
            logger.error(f"Failed to get image description: {e}")
            return None

    async def _detect_objects(self, image_data: bytes) -> List[dict]:
        """检测物体"""
        try:
            result = await self.vision_service.understand_from_bytes(
                image_data=image_data,
                prompt="列出图片中的所有物体，以 JSON 数组格式返回，每个物体包含 name 和 confidence 字段。",
                max_tokens=500,
            )
            # 简化实现：返回文本描述
            # 实际应解析 JSON 返回结构化数据
            return [{"name": result.answer, "confidence": 0.9}]
        except Exception as e:
            logger.error(f"Failed to detect objects: {e}")
            return None

    async def _recognize_scene(self, image_data: bytes) -> str:
        """识别场景"""
        try:
            result = await self.vision_service.understand_from_bytes(
                image_data=image_data,
                prompt="这张图片的场景类型是什么？（如：室内、室外、自然、城市等）只返回场景类型。",
                max_tokens=50,
            )
            return result.answer.strip()
        except Exception as e:
            logger.error(f"Failed to recognize scene: {e}")
            return None

    def _extract_colors(self, image_data: bytes) -> List[str]:
        """提取主要颜色"""
        try:
            image = Image.open(io.BytesIO(image_data))

            # 转换为 RGB
            if image.mode != "RGB":
                image = image.convert("RGB")

            # 缩小图像以加快处理
            image.thumbnail((100, 100))

            # 获取颜色直方图（简化实现）
            colors = image.getcolors(maxcolors=10)

            if not colors:
                return []

            # 按频率排序
            colors.sort(key=lambda x: x[0], reverse=True)

            # 转换为十六进制颜色
            hex_colors = []
            for count, color in colors[:5]:  # 取前 5 种颜色
                if isinstance(color, tuple) and len(color) == 3:
                    hex_color = "#{:02x}{:02x}{:02x}".format(*color)
                    hex_colors.append(hex_color)

            return hex_colors

        except Exception as e:
            logger.error(f"Failed to extract colors: {e}")
            return []

    def _extract_metadata(self, image_data: bytes) -> dict:
        """提取图像元数据"""
        try:
            image = Image.open(io.BytesIO(image_data))

            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image_data),
            }

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return {}

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
