"""
OCR (Optical Character Recognition) service
"""

import base64
import io
import time
from typing import List, Optional

import httpx
from paddleocr import PaddleOCR
from PIL import Image

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.multimodal import OCRRequest, OCRResponse, OCRTextBlock

logger = get_logger(__name__)


class OCRService:
    """OCR 识别服务"""

    def __init__(self):
        self.provider = settings.OCR_PROVIDER
        self.ocr_engine = None

        if self.provider == "paddleocr":
            self._load_paddleocr()

    def _load_paddleocr(self):
        """加载 PaddleOCR 模型"""
        try:
            logger.info(f"Loading PaddleOCR: languages={settings.OCR_LANGUAGES}, use_gpu={settings.OCR_USE_GPU}")

            # 初始化 PaddleOCR
            self.ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang="ch",  # 支持中英文
                use_gpu=settings.OCR_USE_GPU,
                show_log=False,
            )

            logger.info("PaddleOCR loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load PaddleOCR: {e}")
            # 不抛出异常，允许服务启动（降级模式）

    async def recognize(self, request: OCRRequest) -> OCRResponse:
        """
        OCR 识别

        Args:
            request: OCR 请求

        Returns:
            OCR 响应
        """
        # 获取图像数据
        if request.image_base64:
            image_data = base64.b64decode(request.image_base64)
        elif request.image_url:
            image_data = await self._download_image(request.image_url)
        else:
            raise ValueError("Either image_url or image_base64 must be provided")

        # 识别
        response = await self.recognize_from_bytes(
            image_data=image_data,
            languages=request.languages,
            detect_orientation=request.detect_orientation,
            confidence_threshold=request.confidence_threshold,
        )

        return response

    async def recognize_from_bytes(
        self,
        image_data: bytes,
        languages: Optional[List[str]] = None,
        detect_orientation: bool = True,
        confidence_threshold: Optional[float] = None,
    ) -> OCRResponse:
        """
        从图像字节识别

        Args:
            image_data: 图像数据
            languages: 语言列表
            detect_orientation: 是否检测方向
            confidence_threshold: 置信度阈值

        Returns:
            OCR 响应
        """
        start_time = time.time()

        if self.provider == "paddleocr":
            result = await self._recognize_with_paddleocr(image_data, confidence_threshold)
        elif self.provider == "easyocr":
            result = await self._recognize_with_easyocr(image_data, languages, confidence_threshold)
        else:
            raise ValueError(f"Unsupported OCR provider: {self.provider}")

        processing_time_ms = (time.time() - start_time) * 1000

        return OCRResponse(
            text_blocks=result["text_blocks"],
            full_text=result["full_text"],
            language=result["language"],
            processing_time_ms=processing_time_ms,
        )

    async def _recognize_with_paddleocr(
        self, image_data: bytes, confidence_threshold: Optional[float]
    ) -> dict:
        """使用 PaddleOCR 识别"""
        if not self.ocr_engine:
            raise RuntimeError("PaddleOCR not loaded")

        try:
            # 加载图像
            image = Image.open(io.BytesIO(image_data))

            # 转换为 RGB（如果是 RGBA）
            if image.mode != "RGB":
                image = image.convert("RGB")

            # 执行 OCR
            result = self.ocr_engine.ocr(image, cls=True)

            # 解析结果
            text_blocks = []
            full_text_parts = []
            threshold = confidence_threshold or settings.OCR_CONFIDENCE_THRESHOLD

            if result and result[0]:
                for line in result[0]:
                    bbox = line[0]  # 边界框
                    text_info = line[1]  # (文本, 置信度)
                    text = text_info[0]
                    confidence = text_info[1]

                    # 过滤低置信度结果
                    if confidence < threshold:
                        continue

                    # 转换边界框格式
                    bbox_int = [[int(x), int(y)] for x, y in bbox]

                    text_blocks.append(
                        OCRTextBlock(
                            text=text,
                            confidence=float(confidence),
                            bbox=bbox_int,
                        )
                    )

                    full_text_parts.append(text)

            full_text = "\n".join(full_text_parts)

            # 检测主要语言（简化实现）
            language = "zh" if any("\u4e00" <= c <= "\u9fff" for c in full_text) else "en"

            return {
                "text_blocks": text_blocks,
                "full_text": full_text,
                "language": language,
            }

        except Exception as e:
            logger.error(f"PaddleOCR recognition failed: {e}", exc_info=True)
            raise

    async def _recognize_with_easyocr(
        self, image_data: bytes, languages: Optional[List[str]], confidence_threshold: Optional[float]
    ) -> dict:
        """使用 EasyOCR 识别"""
        # TODO: 实现 EasyOCR 集成
        raise NotImplementedError("EasyOCR not implemented yet")

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
