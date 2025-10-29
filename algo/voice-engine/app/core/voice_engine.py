"""
Voice Engine Core - 语音引擎核心
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.asr_engine import ASREngine
from app.core.circuit_breaker import CircuitBreaker
from app.core.config import get_settings
from app.core.observability import track_asr_metrics, track_tts_metrics, track_vad_metrics
from app.core.tts_engine import TTSEngine
from app.core.vad_engine import VADEngine

logger = logging.getLogger(__name__)
settings = get_settings()


class VoiceEngine:
    """语音引擎"""

    def __init__(self) -> None:
        """初始化语音引擎"""
        self.asr_engine = None
        self.tts_engine = None
        self.vad_engine = None

        # 熔断器
        self.asr_circuit_breaker = None
        self.tts_circuit_breaker = None
        self.vad_circuit_breaker = None

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

    async def initialize(self) -> None:
        """初始化所有组件"""
        logger.info("Initializing Voice Engine components...")

        # 初始化熔断器
        if settings.CIRCUIT_BREAKER_ENABLED:
            self.asr_circuit_breaker = CircuitBreaker(
                failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
                name="asr_circuit_breaker",
            )
            self.tts_circuit_breaker = CircuitBreaker(
                failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
                name="tts_circuit_breaker",
            )
            self.vad_circuit_breaker = CircuitBreaker(
                failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
                name="vad_circuit_breaker",
            )

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

    @track_asr_metrics(model="base", language="zh")
    async def speech_to_text(
        self,
        audio_data: bytes,
        language: str = "zh",
        model: str = "base",
    ) -> dict:
        """
        语音识别（带超时、重试和熔断）

        Args:
            audio_data: 音频数据
            language: 语言代码
            model: Whisper 模型

        Returns:
            识别结果
        """
        self.stats["total_asr_requests"] += 1

        async def _do_transcribe():
            """执行识别（内部函数）"""
            return await self.asr_engine.transcribe(
                audio_data=audio_data,
                language=language,
                model=model,
            )

        try:
            # 添加超时
            result = await asyncio.wait_for(
                # 通过熔断器调用（如果启用）
                self.asr_circuit_breaker.call(_do_transcribe)
                if self.asr_circuit_breaker
                else _do_transcribe(),
                timeout=settings.ASR_TIMEOUT_SECONDS,
            )

            self.stats["successful_asr"] += 1
            self.stats["total_audio_duration"] += result.get("duration", 0)

            return result

        except TimeoutError:
            logger.error(f"ASR timeout after {settings.ASR_TIMEOUT_SECONDS}s")
            raise Exception(f"ASR timeout after {settings.ASR_TIMEOUT_SECONDS}s")
        except Exception as e:
            logger.error(f"ASR failed: {e}", exc_info=True)
            raise

    @track_tts_metrics(voice="zh-CN-XiaoxiaoNeural", provider="edge")
    async def text_to_speech_stream(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> AsyncIterator[bytes]:
        """
        文本转语音（流式，带超时和熔断）

        Args:
            text: 文本
            voice: 语音名称
            rate: 语速
            pitch: 音调

        Yields:
            音频数据块
        """
        self.stats["total_tts_requests"] += 1

        async def _do_synthesize_stream():
            """执行合成（内部函数）"""
            async for chunk in self.tts_engine.synthesize_stream(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            ):
                yield chunk

        try:
            # 流式处理：添加超时到整个流
            stream_gen = (
                self.tts_circuit_breaker.call(_do_synthesize_stream)
                if self.tts_circuit_breaker
                else _do_synthesize_stream()
            )

            async for chunk in stream_gen:
                yield chunk

            self.stats["successful_tts"] += 1

        except TimeoutError:
            logger.error(f"TTS timeout after {settings.TTS_TIMEOUT_SECONDS}s")
            raise Exception(f"TTS timeout after {settings.TTS_TIMEOUT_SECONDS}s")
        except Exception as e:
            logger.error(f"TTS failed: {e}", exc_info=True)
            raise

    @track_vad_metrics()
    async def detect_voice_activity(
        self,
        audio_data: bytes,
        threshold: float = 0.5,
    ) -> list[dict]:
        """
        语音活动检测（带超时和熔断）

        Args:
            audio_data: 音频数据
            threshold: 检测阈值

        Returns:
            语音片段列表
        """
        self.stats["total_vad_requests"] += 1

        async def _do_detect():
            """执行检测（内部函数）"""
            return await self.vad_engine.detect(
                audio_data=audio_data,
                threshold=threshold,
            )

        try:
            # 添加超时
            segments = await asyncio.wait_for(
                # 通过熔断器调用（如果启用）
                self.vad_circuit_breaker.call(_do_detect)
                if self.vad_circuit_breaker
                else _do_detect(),
                timeout=settings.VAD_TIMEOUT_SECONDS,
            )

            self.stats["successful_vad"] += 1

            return segments

        except TimeoutError:
            logger.error(f"VAD timeout after {settings.VAD_TIMEOUT_SECONDS}s")
            raise Exception(f"VAD timeout after {settings.VAD_TIMEOUT_SECONDS}s")
        except Exception as e:
            logger.error(f"VAD failed: {e}", exc_info=True)
            raise

    def list_available_voices(self) -> list[dict]:
        """列出可用语音"""
        return self.tts_engine.list_voices()

    async def get_stats(self) -> dict:
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

    async def denoise_audio(self, audio_data: bytes, strength: float = 0.5, **kwargs) -> bytes:
        """
        音频降噪处理

        Args:
            audio_data: 原始音频数据
            strength: 降噪强度 (0.0-1.0)
            **kwargs: 其他参数

        Returns:
            降噪后的音频数据
        """
        try:
            import io

            import numpy as np
            from pydub import AudioSegment
            from scipy import signal

            # 将字节转换为AudioSegment
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            # 转换为numpy数组
            samples = np.array(audio.get_array_of_samples())

            # 应用低通滤波器去除高频噪声
            nyquist = audio.frame_rate // 2
            cutoff = 3000  # 3kHz 低通滤波
            normal_cutoff = cutoff / nyquist

            # 设计巴特沃斯滤波器
            b, a = signal.butter(4, normal_cutoff, btype="low", analog=False)
            filtered_samples = signal.filtfilt(b, a, samples)

            # 应用降噪强度
            denoised_samples = samples * (1 - strength) + filtered_samples * strength
            denoised_samples = denoised_samples.astype(np.int16)

            # 转换回AudioSegment
            denoised_audio = AudioSegment(
                denoised_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels,
            )

            # 导出为字节
            output = io.BytesIO()
            denoised_audio.export(output, format="wav")
            output.seek(0)

            logger.info(f"Audio denoised with strength={strength}")
            return output.read()

        except ImportError as e:
            logger.error(f"Missing required package for audio processing: {e}")
            raise Exception("Audio processing dependencies not installed (numpy, scipy, pydub)")
        except Exception as e:
            logger.error(f"Audio denoising failed: {e}", exc_info=True)
            raise

    async def enhance_audio(
        self, audio_data: bytes, normalize: bool = True, denoise_strength: float = 0.3, **kwargs
    ) -> bytes:
        """
        音频增强处理（降噪 + 音量标准化）

        Args:
            audio_data: 原始音频数据
            normalize: 是否进行音量标准化
            denoise_strength: 降噪强度
            **kwargs: 其他参数

        Returns:
            增强后的音频数据
        """
        try:
            import io

            from pydub import AudioSegment
            from pydub.effects import normalize as pydub_normalize

            # 先进行降噪
            denoised_data = await self.denoise_audio(audio_data, strength=denoise_strength)

            # 将字节转换为AudioSegment
            audio = AudioSegment.from_file(io.BytesIO(denoised_data))

            # 音量标准化
            if normalize:
                audio = pydub_normalize(audio)

            # 可选：动态范围压缩
            # audio = audio.compress_dynamic_range(threshold=-20.0, ratio=4.0)

            # 导出为字节
            output = io.BytesIO()
            audio.export(output, format="wav")
            output.seek(0)

            logger.info(f"Audio enhanced (denoise={denoise_strength}, normalize={normalize})")
            return output.read()

        except Exception as e:
            logger.error(f"Audio enhancement failed: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Cleaning up Voice Engine...")

        if self.asr_engine:
            await self.asr_engine.cleanup()

        if self.tts_engine:
            await self.tts_engine.cleanup()

        if self.vad_engine:
            await self.vad_engine.cleanup()

        logger.info("Voice Engine cleanup complete")
