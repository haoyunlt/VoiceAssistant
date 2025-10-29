"""
Image Understanding Service
"""

import io
import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


class ImageUnderstandingService:
    """图像理解服务"""

    def __init__(self, ocr_service=None, vision_model=None):
        self.ocr_service = ocr_service
        self.vision_model = vision_model

    async def understand_image(
        self,
        image_data: bytes,
        tasks: list[str] | None = None
    ) -> dict[str, Any]:
        """全面理解图像"""
        if tasks is None:
            tasks = ["ocr", "caption", "objects"]

        result = {"image_size": len(image_data)}

        # 加载图像
        image = Image.open(io.BytesIO(image_data))
        result["dimensions"] = {"width": image.width, "height": image.height}

        # 执行不同任务
        if "ocr" in tasks and self.ocr_service:
            result["text"] = await self._extract_text(image)

        if "caption" in tasks and self.vision_model:
            result["caption"] = await self._generate_caption(image)

        if "objects" in tasks and self.vision_model:
            result["objects"] = await self._detect_objects(image)

        if "scene" in tasks and self.vision_model:
            result["scene"] = await self._classify_scene(image)

        logger.info(f"Image understanding completed: {list(result.keys())}")
        return result

    async def _extract_text(self, image: Image.Image) -> dict[str, Any]:
        """OCR文本提取"""
        try:
            # 使用OCR服务
            if self.ocr_service:
                text = await self.ocr_service.extract_text(image)
            else:
                # Fallback to pytesseract
                import pytesseract
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')

            return {
                "text": text.strip(),
                "length": len(text.strip())
            }
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {"text": "", "error": str(e)}

    async def _generate_caption(self, image: Image.Image) -> dict[str, Any]:
        """生成图像描述"""
        try:
            if self.vision_model:
                caption = await self.vision_model.generate_caption(image)
            else:
                caption = "Image caption generation not available"

            return {
                "caption": caption,
                "confidence": 0.85
            }
        except Exception as e:
            logger.error(f"Caption generation failed: {e}")
            return {"caption": "", "error": str(e)}

    async def _detect_objects(self, image: Image.Image) -> list[dict]:
        """物体检测"""
        try:
            if self.vision_model:
                objects = await self.vision_model.detect_objects(image)
            else:
                objects = []

            return objects
        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return []

    async def _classify_scene(self, image: Image.Image) -> dict[str, Any]:
        """场景分类"""
        try:
            if self.vision_model:
                scene = await self.vision_model.classify_scene(image)
            else:
                scene = {"category": "unknown", "confidence": 0.0}

            return scene
        except Exception as e:
            logger.error(f"Scene classification failed: {e}")
            return {"category": "unknown", "error": str(e)}

    async def answer_visual_question(
        self,
        image_data: bytes,
        question: str
    ) -> str:
        """视觉问答"""
        try:
            image = Image.open(io.BytesIO(image_data))

            if self.vision_model:
                answer = await self.vision_model.answer_question(image, question)
            else:
                # Fallback: basic understanding
                understanding = await self.understand_image(image_data)
                answer = f"Image contains: {understanding.get('caption', {}).get('caption', 'unknown content')}"

            return answer
        except Exception as e:
            logger.error(f"Visual QA failed: {e}")
            return f"Error: {str(e)}"
