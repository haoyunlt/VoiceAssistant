"""
OCR (Optical Character Recognition) service
"""

import base64
import io
import logging
import time

import httpx
from paddleocr import PaddleOCR
from PIL import Image

from app.core.config import settings
from app.models.multimodal import OCRRequest, OCRResponse, OCRTextBlock

logger = logging.getLogger(__name__)


class OCRService:
    """OCR 识别服务"""

    def __init__(self):
        self.provider = settings.OCR_PROVIDER
        self.ocr_engine = None
        self.easyocr_reader = None

        if self.provider == "paddleocr":
            self._load_paddleocr()
        elif self.provider == "easyocr":
            self._load_easyocr()

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

    def _load_easyocr(self):
        """加载 EasyOCR 模型"""
        try:
            import easyocr

            # 获取语言列表
            languages = settings.OCR_LANGUAGES or ['ch_sim', 'en']

            logger.info(f"Loading EasyOCR: languages={languages}, use_gpu={settings.OCR_USE_GPU}")

            # 初始化 EasyOCR Reader
            self.easyocr_reader = easyocr.Reader(
                languages,
                gpu=settings.OCR_USE_GPU,
                verbose=False,
                download_enabled=True  # 自动下载模型
            )

            logger.info(f"EasyOCR loaded successfully with languages: {languages}")

        except ImportError:
            logger.warning("EasyOCR not installed. Install with: pip install easyocr")
            self.easyocr_reader = None
        except Exception as e:
            logger.error(f"Failed to load EasyOCR: {e}", exc_info=True)
            self.easyocr_reader = None

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
        languages: list[str] | None = None,
        detect_orientation: bool = True,
        confidence_threshold: float | None = None,
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
        self, image_data: bytes, confidence_threshold: float | None
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
        self, image_data: bytes, languages: list[str] | None, confidence_threshold: float | None
    ) -> dict:
        """
        使用 EasyOCR 识别

        Args:
            image_data: 图像数据
            languages: 语言列表（可选，覆盖初始化时的语言）
            confidence_threshold: 置信度阈值

        Returns:
            包含text_blocks、full_text、language的字典
        """
        if not self.easyocr_reader:
            raise RuntimeError("EasyOCR not loaded. Please initialize with provider='easyocr'")

        try:
            import numpy as np
            from PIL import Image

            # 加载图像
            image = Image.open(io.BytesIO(image_data))

            # 转换为 RGB
            if image.mode != "RGB":
                image = image.convert("RGB")

            # 转换为numpy数组
            image_np = np.array(image)

            # 执行 OCR
            # readtext返回：[(bbox, text, confidence), ...]
            results = self.easyocr_reader.readtext(
                image_np,
                detail=1,  # 返回详细信息（边界框和置信度）
                paragraph=False,  # 不合并段落
                batch_size=10
            )

            # 解析结果
            text_blocks = []
            full_text_parts = []
            threshold = confidence_threshold or settings.OCR_CONFIDENCE_THRESHOLD

            for bbox, text, confidence in results:
                # 过滤低置信度结果
                if confidence < threshold:
                    continue

                # EasyOCR的bbox格式：[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                # 转换为整数坐标
                bbox_int = [[int(x), int(y)] for x, y in bbox]

                text_blocks.append(
                    OCRTextBlock(
                        text=text,
                        confidence=float(confidence),
                        bbox=bbox_int,
                    )
                )

                full_text_parts.append(text)

            # 合并为完整文本
            full_text = "\n".join(full_text_parts)

            # 检测主要语言（简化实现）
            # 检测中文字符
            has_chinese = any('\u4e00' <= c <= '\u9fff' for c in full_text)
            # 检测日文字符
            has_japanese = any('\u3040' <= c <= '\u30ff' for c in full_text)
            # 检测韩文字符
            has_korean = any('\uac00' <= c <= '\ud7af' for c in full_text)

            if has_chinese:
                language = "zh"
            elif has_japanese:
                language = "ja"
            elif has_korean:
                language = "ko"
            else:
                language = "en"

            logger.info(
                f"EasyOCR recognized {len(text_blocks)} text blocks, "
                f"total text length: {len(full_text)}, language: {language}"
            )

            return {
                "text_blocks": text_blocks,
                "full_text": full_text,
                "language": language,
            }

        except Exception as e:
            logger.error(f"EasyOCR recognition failed: {e}", exc_info=True)
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
