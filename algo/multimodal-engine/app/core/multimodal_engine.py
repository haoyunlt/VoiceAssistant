import logging
import time
from typing import Any, Dict, Optional

from app.core.ocr_engine import OCREngine
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

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "ocr_requests": 0,
            "vision_requests": 0,
            "video_requests": 0,
            "avg_latency_ms": 0.0,
        }
        self._latencies = []

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
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        self.stats["ocr_requests"] += 1

        try:
            result = await self.ocr_engine.recognize(
                image_data=image_data,
                language=language,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            self.stats["successful_requests"] += 1
            latency = (time.time() - start_time) * 1000
            self._latencies.append(latency)
            self._update_avg_latency()

            result["duration_ms"] = latency
            return result

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Error in OCR: {e}", exc_info=True)
            raise

    async def vision_understand(
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
                "confidence": 0.92,
                "duration_ms": 2000
            }
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        self.stats["vision_requests"] += 1

        try:
            result = await self.vision_engine.understand(
                image_data=image_data,
                prompt=prompt,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            self.stats["successful_requests"] += 1
            latency = (time.time() - start_time) * 1000
            self._latencies.append(latency)
            self._update_avg_latency()

            result["duration_ms"] = latency
            return result

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Error in vision understanding: {e}", exc_info=True)
            raise

    async def vision_detect(
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
                ],
                "duration_ms": 500
            }
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        self.stats["vision_requests"] += 1

        try:
            result = await self.vision_engine.detect(
                image_data=image_data,
                detect_type=detect_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            self.stats["successful_requests"] += 1
            latency = (time.time() - start_time) * 1000
            self._latencies.append(latency)
            self._update_avg_latency()

            result["duration_ms"] = latency
            return result

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Error in vision detection: {e}", exc_info=True)
            raise

    async def video_analyze(
        self,
        video_data: bytes,
        analysis_type: str = "summary",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        self.stats["video_requests"] += 1

        try:
            result = await self.video_engine.analyze(
                video_data=video_data,
                analysis_type=analysis_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            self.stats["successful_requests"] += 1
            latency = (time.time() - start_time) * 1000
            self._latencies.append(latency)
            self._update_avg_latency()

            result["duration_ms"] = latency
            return result

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Error in video analysis: {e}", exc_info=True)
            raise

    def _update_avg_latency(self):
        """更新平均延迟"""
        if self._latencies:
            self.stats["avg_latency_ms"] = sum(self._latencies) / len(self._latencies)

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "ocr_engine_stats": await self.ocr_engine.get_stats(),
            "vision_engine_stats": await self.vision_engine.get_stats(),
            "video_engine_stats": await self.video_engine.get_stats(),
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
