"""
Voice Engine Core - 语音引擎核心
"""

import logging
from typing import AsyncIterator, Dict, List

from app.core.asr_engine import ASREngine
from app.core.tts_engine import TTSEngine
from app.core.vad_engine import VADEngine

logger = logging.getLogger(__name__)


class VoiceEngine:
    """语音引擎"""

    def __init__(self):
        """初始化语音引擎"""
        self.asr_engine = None
        self.tts_engine = None
        self.vad_engine = None

        # 统计信息
        self.stats = {
            "total_asr_requests": 0,
            "total_tts_requests": 0,
            "total_vad_requests": 0,
            "successful_asr": 0,
            "successful_tts": 0,
            "successful_vad": 0,
            "total_audio_duration": 0,  # 秒
        }

        logger.info("Voice Engine created")

    async def initialize(self):
        """初始化所有组件"""
        logger.info("Initializing Voice Engine components...")

        # 初始化 ASR 引擎
        self.asr_engine = ASREngine()
        await self.asr_engine.initialize()

        # 初始化 TTS 引擎
        self.tts_engine = TTSEngine()
        await self.tts_engine.initialize()

        # 初始化 VAD 引擎
        self.vad_engine = VADEngine()
        await self.vad_engine.initialize()

        logger.info("Voice Engine initialized successfully")

    async def speech_to_text(
        self,
        audio_data: bytes,
        language: str = "zh",
        model: str = "base",
    ) -> Dict:
        """
        语音识别

        Args:
            audio_data: 音频数据
            language: 语言代码
            model: Whisper 模型

        Returns:
            识别结果
        """
        self.stats["total_asr_requests"] += 1

        try:
            result = await self.asr_engine.transcribe(
                audio_data=audio_data,
                language=language,
                model=model,
            )

            self.stats["successful_asr"] += 1
            self.stats["total_audio_duration"] += result.get("duration", 0)

            return result

        except Exception as e:
            logger.error(f"ASR failed: {e}", exc_info=True)
            raise

    async def text_to_speech_stream(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> AsyncIterator[bytes]:
        """
        文本转语音（流式）

        Args:
            text: 文本
            voice: 语音名称
            rate: 语速
            pitch: 音调

        Yields:
            音频数据块
        """
        self.stats["total_tts_requests"] += 1

        try:
            async for chunk in self.tts_engine.synthesize_stream(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            ):
                yield chunk

            self.stats["successful_tts"] += 1

        except Exception as e:
            logger.error(f"TTS failed: {e}", exc_info=True)
            raise

    async def detect_voice_activity(
        self,
        audio_data: bytes,
        threshold: float = 0.5,
    ) -> List[Dict]:
        """
        语音活动检测

        Args:
            audio_data: 音频数据
            threshold: 检测阈值

        Returns:
            语音片段列表
        """
        self.stats["total_vad_requests"] += 1

        try:
            segments = await self.vad_engine.detect(
                audio_data=audio_data,
                threshold=threshold,
            )

            self.stats["successful_vad"] += 1

            return segments

        except Exception as e:
            logger.error(f"VAD failed: {e}", exc_info=True)
            raise

    def list_available_voices(self) -> List[Dict]:
        """列出可用语音"""
        return self.tts_engine.list_voices()

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "asr_success_rate": (
                self.stats["successful_asr"] / self.stats["total_asr_requests"]
                if self.stats["total_asr_requests"] > 0
                else 0
            ),
            "tts_success_rate": (
                self.stats["successful_tts"] / self.stats["total_tts_requests"]
                if self.stats["total_tts_requests"] > 0
                else 0
            ),
            "vad_success_rate": (
                self.stats["successful_vad"] / self.stats["total_vad_requests"]
                if self.stats["total_vad_requests"] > 0
                else 0
            ),
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up Voice Engine...")

        if self.asr_engine:
            await self.asr_engine.cleanup()

        if self.tts_engine:
            await self.tts_engine.cleanup()

        if self.vad_engine:
            await self.vad_engine.cleanup()

        logger.info("Voice Engine cleanup complete")
