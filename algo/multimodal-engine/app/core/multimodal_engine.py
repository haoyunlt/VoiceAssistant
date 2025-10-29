import logging
import time
from typing import Any

from app.core.exceptions import OCRException, VideoException, VisionException
from app.core.ocr_engine import OCREngine
from app.core.stats import StatsTracker
from app.core.video_engine import VideoEngine
from app.core.vision_engine import VisionEngine

logger = logging.getLogger(__name__)


class MultimodalEngine:
    """
    多模态理解引擎，统一管理 OCR、图像理解、视频分析等功能。
    """

    def __init__(
        self,
        ocr_engine: OCREngine,
        vision_engine: VisionEngine,
        video_engine: VideoEngine,
    ):
        self.ocr_engine = ocr_engine
        self.vision_engine = vision_engine
        self.video_engine = video_engine

        # Use bounded stats trackers to prevent memory leaks
        self.stats_tracker = StatsTracker(max_latency_samples=1000)
        self.ocr_stats = StatsTracker(max_latency_samples=1000)
        self.vision_stats = StatsTracker(max_latency_samples=1000)
        self.video_stats = StatsTracker(max_latency_samples=1000)

        logger.info("MultimodalEngine initialized.")

    async def initialize(self):
        """初始化所有引擎"""
        logger.info("Initializing Multimodal Engine components...")
        await self.ocr_engine.initialize()
        await self.vision_engine.initialize()
        await self.video_engine.initialize()
        logger.info("Multimodal Engine components initialized.")

    async def ocr(
        self,
        image_data: bytes,
        language: str = "auto",
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        OCR 文字识别。

        Args:
            image_data: 图片二进制数据
            language: 语言代码
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "text": "识别的文本",
                "confidence": 0.95,
                "regions": [{"text": "...", "bbox": [x, y, w, h], "confidence": 0.9}],
                "duration_ms": 150
            }

        Raises:
            OCRException: If OCR processing fails
        """
        start_time = time.time()

        try:
            result = await self.ocr_engine.recognize(
                image_data=image_data,
                language=language,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            latency = (time.time() - start_time) * 1000
            self.stats_tracker.record_success(latency)
            self.ocr_stats.record_success(latency)

            result["duration_ms"] = latency
            return result

        except OCRException:
            # Re-raise known OCR exceptions
            self.stats_tracker.record_failure()
            self.ocr_stats.record_failure()
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            self.stats_tracker.record_failure()
            self.ocr_stats.record_failure()
            logger.error(f"Unexpected error in OCR: {e}", exc_info=True)
            raise OCRException(
                "OCR processing failed",
                details={"error_type": type(e).__name__}
            )

    async def vision_understand(
        self,
        image_data: bytes,
        prompt: str = "Describe this image in detail.",
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
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
                "confidence": 0.92,
                "duration_ms": 2000
            }

        Raises:
            VisionException: If vision processing fails
        """
        start_time = time.time()

        try:
            result = await self.vision_engine.understand(
                image_data=image_data,
                prompt=prompt,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            latency = (time.time() - start_time) * 1000
            self.stats_tracker.record_success(latency)
            self.vision_stats.record_success(latency)

            result["duration_ms"] = latency
            return result

        except VisionException:
            # Re-raise known vision exceptions
            self.stats_tracker.record_failure()
            self.vision_stats.record_failure()
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            self.stats_tracker.record_failure()
            self.vision_stats.record_failure()
            logger.error(f"Unexpected error in vision understanding: {e}", exc_info=True)
            raise VisionException(
                "Vision understanding failed",
                details={"error_type": type(e).__name__}
            )

    async def vision_detect(
        self,
        image_data: bytes,
        detect_type: str = "objects",
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
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
                ],
                "duration_ms": 500
            }

        Raises:
            VisionException: If detection fails
        """
        start_time = time.time()

        try:
            result = await self.vision_engine.detect(
                image_data=image_data,
                detect_type=detect_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            latency = (time.time() - start_time) * 1000
            self.stats_tracker.record_success(latency)
            self.vision_stats.record_success(latency)

            result["duration_ms"] = latency
            return result

        except VisionException:
            self.stats_tracker.record_failure()
            self.vision_stats.record_failure()
            raise
        except Exception as e:
            self.stats_tracker.record_failure()
            self.vision_stats.record_failure()
            logger.error(f"Unexpected error in vision detection: {e}", exc_info=True)
            raise VisionException(
                "Vision detection failed",
                details={"error_type": type(e).__name__}
            )

    async def video_analyze(
        self,
        video_data: bytes,
        analysis_type: str = "summary",
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        视频分析。

        Args:
            video_data: 视频二进制数据
            analysis_type: 分析类型 (summary, keyframes, objects, speech)
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "summary": "视频摘要",
                "keyframes": [...],
                "objects": [...],
                "speech": [...],
                "duration_ms": 5000
            }

        Raises:
            VideoException: If video analysis fails
        """
        start_time = time.time()

        try:
            result = await self.video_engine.analyze(
                video_data=video_data,
                analysis_type=analysis_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            latency = (time.time() - start_time) * 1000
            self.stats_tracker.record_success(latency)
            self.video_stats.record_success(latency)

            result["duration_ms"] = latency
            return result

        except VideoException:
            self.stats_tracker.record_failure()
            self.video_stats.record_failure()
            raise
        except Exception as e:
            self.stats_tracker.record_failure()
            self.video_stats.record_failure()
            logger.error(f"Unexpected error in video analysis: {e}", exc_info=True)
            raise VideoException(
                "Video analysis failed",
                details={"error_type": type(e).__name__}
            )

    async def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "overall": self.stats_tracker.get_stats(),
            "ocr": self.ocr_stats.get_stats(),
            "vision": self.vision_stats.get_stats(),
            "video": self.video_stats.get_stats(),
            "engines": {
                "ocr_engine": await self.ocr_engine.get_stats(),
                "vision_engine": await self.vision_engine.get_stats(),
                "video_engine": await self.video_engine.get_stats(),
            },
        }

    async def is_ready(self) -> bool:
        """检查是否准备就绪"""
        return (
            await self.ocr_engine.is_ready()
            and await self.vision_engine.is_ready()
            and await self.video_engine.is_ready()
        )

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up Multimodal Engine resources...")
        if self.ocr_engine:
            await self.ocr_engine.cleanup()
        if self.vision_engine:
            await self.vision_engine.cleanup()
        if self.video_engine:
            await self.video_engine.cleanup()
        logger.info("Multimodal Engine resources cleaned up.")
