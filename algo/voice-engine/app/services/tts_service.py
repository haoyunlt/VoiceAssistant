"""
TTS (Text-to-Speech) service
"""

import base64
import hashlib
import os
import time
from typing import AsyncGenerator, List, Optional

import edge_tts

from app.core.config import settings
from app.core.logging_config import get_logger
from app.infrastructure.tts_cache import TTSRedisCache
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    """TTS 合成服务"""

    def __init__(self, redis_url: str = None, max_cache_size_mb: int = 1000):
        self.provider = settings.TTS_PROVIDER

        # 初始化 Redis 缓存
        redis_url = redis_url or settings.REDIS_URL
        self.cache = TTSRedisCache(
            redis_url=redis_url,
            ttl_days=30,
            max_cache_size_mb=max_cache_size_mb,
        )

        # 初始化 Azure Speech Service（如果启用）
        self.azure_service = None
        if self.provider == "azure":
            self._initialize_azure()

        logger.info(f"TTSService initialized with provider={self.provider}, cache={self.cache.health_check()['backend']}")

    def _initialize_azure(self):
        """初始化Azure Speech Service"""
        try:
            from app.services.azure_speech_service import AzureSpeechService

            subscription_key = os.getenv("AZURE_SPEECH_KEY")
            region = os.getenv("AZURE_SPEECH_REGION", "eastus")

            if not subscription_key:
                logger.warning("AZURE_SPEECH_KEY not set, Azure TTS will not be available")
                return

            self.azure_service = AzureSpeechService(
                subscription_key=subscription_key,
                region=region
            )

            logger.info("Azure Speech Service initialized for TTS")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Speech Service: {e}")

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """
        文本转语音

        Args:
            request: TTS 请求

        Returns:
            TTS 响应
        """
        start_time = time.time()

        # 检查缓存（从 Redis）
        voice = request.voice or settings.TTS_VOICE
        rate = request.rate or settings.TTS_RATE
        pitch = request.pitch or settings.TTS_PITCH
        format = request.format or "mp3"

        cached_audio_bytes = self.cache.get(
            text=request.text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            format=format,
        )

        if cached_audio_bytes:
            logger.info("TTS cache hit")
            audio_base64 = base64.b64encode(cached_audio_bytes).decode("utf-8")
            return TTSResponse(
                audio_base64=audio_base64,
                duration_ms=0,  # 缓存的不计算时长
                processing_time_ms=(time.time() - start_time) * 1000,
                cached=True,
            )

        # 根据 provider 选择合成方式
        if self.provider == "edge":
            audio_data = await self._synthesize_with_edge(request)
        elif self.provider == "azure":
            audio_data = await self._synthesize_with_azure(request)
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

        # 存入缓存（到 Redis）
        self.cache.set(
            text=request.text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            format=format,
            audio_data=audio_data,
        )

        # 编码为 Base64
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        processing_time_ms = (time.time() - start_time) * 1000

        return TTSResponse(
            audio_base64=audio_base64,
            duration_ms=0,  # TODO: 计算实际音频时长
            processing_time_ms=processing_time_ms,
            cached=False,
        )

    async def synthesize_stream(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """
        流式文本转语音

        Args:
            request: TTS 请求

        Yields:
            音频数据块
        """
        if self.provider == "edge":
            async for chunk in self._synthesize_stream_edge(request):
                yield chunk
        else:
            # 其他 provider 暂不支持流式
            audio_data = await self._synthesize_with_edge(request)
            yield audio_data

    async def _synthesize_with_edge(self, request: TTSRequest) -> bytes:
        """使用 Edge TTS 合成"""
        try:
            voice = request.voice or settings.TTS_VOICE
            rate = request.rate or settings.TTS_RATE
            pitch = request.pitch or settings.TTS_PITCH

            communicate = edge_tts.Communicate(text=request.text, voice=voice, rate=rate, pitch=pitch)

            # 收集所有音频数据
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            return audio_data

        except Exception as e:
            logger.error(f"Edge TTS synthesis failed: {e}", exc_info=True)
            raise

    async def _synthesize_stream_edge(self, request: TTSRequest) -> AsyncGenerator[bytes, None]:
        """使用 Edge TTS 流式合成"""
        try:
            voice = request.voice or settings.TTS_VOICE
            rate = request.rate or settings.TTS_RATE
            pitch = request.pitch or settings.TTS_PITCH

            communicate = edge_tts.Communicate(text=request.text, voice=voice, rate=rate, pitch=pitch)

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        except Exception as e:
            logger.error(f"Edge TTS stream synthesis failed: {e}", exc_info=True)
            raise

    async def _synthesize_with_azure(self, request: TTSRequest) -> bytes:
        """使用 Azure Speech 合成"""
        if not self.azure_service:
            raise RuntimeError("Azure Speech Service not initialized")

        try:
            # 确保Azure服务已初始化
            if not self.azure_service.initialized:
                await self.azure_service.initialize()

            voice = request.voice or "zh-CN-XiaoxiaoNeural"
            rate = request.rate or "+0%"
            pitch = request.pitch or "+0%"

            # 调用Azure Speech SDK
            audio_data = await self.azure_service.synthesize_to_bytes(
                text=request.text,
                voice_name=voice,
                rate=rate,
                pitch=pitch
            )

            return audio_data

        except Exception as e:
            logger.error(f"Azure TTS synthesis failed: {e}", exc_info=True)
            raise

    async def list_voices(self) -> List[dict]:
        """列出可用的音色"""
        if self.provider == "edge":
            # Edge TTS 支持的中文音色
            return [
                {
                    "name": "zh-CN-XiaoxiaoNeural",
                    "gender": "Female",
                    "language": "zh-CN",
                    "description": "晓晓（女声，活泼）",
                },
                {
                    "name": "zh-CN-YunxiNeural",
                    "gender": "Male",
                    "language": "zh-CN",
                    "description": "云希（男声，自然）",
                },
                {
                    "name": "zh-CN-YunyangNeural",
                    "gender": "Male",
                    "language": "zh-CN",
                    "description": "云扬（男声，新闻播报）",
                },
                {
                    "name": "zh-CN-XiaoyiNeural",
                    "gender": "Female",
                    "language": "zh-CN",
                    "description": "晓伊（女声，温柔）",
                },
                {
                    "name": "zh-CN-YunjianNeural",
                    "gender": "Male",
                    "language": "zh-CN",
                    "description": "云健（男声，运动解说）",
                },
                # 英文音色
                {
                    "name": "en-US-AriaNeural",
                    "gender": "Female",
                    "language": "en-US",
                    "description": "Aria (Female, News)",
                },
                {
                    "name": "en-US-GuyNeural",
                    "gender": "Male",
                    "language": "en-US",
                    "description": "Guy (Male, News)",
                },
            ]
        else:
            return []

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return self.cache.get_stats()

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()

    def health_check(self) -> dict:
        """健康检查"""
        return self.cache.health_check()
