"""
TTS (Text-to-Speech) service
"""

import base64
import hashlib
import time
from typing import AsyncGenerator, List, Optional

import edge_tts

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.voice import TTSRequest, TTSResponse

logger = get_logger(__name__)


class TTSService:
    """TTS 合成服务"""

    def __init__(self):
        self.provider = settings.TTS_PROVIDER
        self.cache: dict = {}  # 简单的内存缓存，生产环境应使用 Redis

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """
        文本转语音

        Args:
            request: TTS 请求

        Returns:
            TTS 响应
        """
        start_time = time.time()

        # 检查缓存
        cache_key = request.cache_key or self._generate_cache_key(request)
        cached_audio = self._get_from_cache(cache_key)

        if cached_audio:
            logger.info(f"TTS cache hit: {cache_key}")
            return TTSResponse(
                audio_base64=cached_audio,
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

        # 编码为 Base64
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # 存入缓存
        self._put_to_cache(cache_key, audio_base64)

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
        # TODO: 实现 Azure Speech SDK 集成
        raise NotImplementedError("Azure Speech synthesis not implemented yet")

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

    def _generate_cache_key(self, request: TTSRequest) -> str:
        """生成缓存键"""
        key_str = f"{request.text}:{request.voice}:{request.rate}:{request.pitch}:{request.format}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[str]:
        """从缓存获取"""
        # TODO: 使用 Redis 缓存
        return self.cache.get(key)

    def _put_to_cache(self, key: str, value: str):
        """存入缓存"""
        # TODO: 使用 Redis 缓存
        self.cache[key] = value
