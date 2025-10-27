"""
VAD (Voice Activity Detection) service
"""

import base64
import io
import time
from typing import Optional

import httpx
import numpy as np
import torch
from pydub import AudioSegment

from app.core.config import settings
import logging
from app.models.voice import VADRequest, VADResponse, VoiceSegment

logger = logging.getLogger(__name__)


class VADService:
    """VAD 语音活动检测服务"""

    def __init__(self):
        self.model = None
        self.utils = None
        self._load_model()

    def _load_model(self):
        """加载 Silero VAD 模型"""
        try:
            logger.info("Loading Silero VAD model")

            # 使用 torch.hub 加载 Silero VAD
            self.model, self.utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )

            logger.info("Silero VAD model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load VAD model: {e}")
            # 不抛出异常，允许服务启动（降级模式）

    async def detect(self, request: VADRequest) -> VADResponse:
        """
        语音活动检测

        Args:
            request: VAD 请求

        Returns:
            VAD 响应
        """
        # 获取音频数据
        if request.audio_base64:
            audio_data = base64.b64decode(request.audio_base64)
        elif request.audio_url:
            audio_data = await self._download_audio(request.audio_url)
        else:
            raise ValueError("Either audio_url or audio_base64 must be provided")

        return await self.detect_from_bytes(audio_data, request.threshold)

    async def detect_from_bytes(
        self, audio_data: bytes, threshold: Optional[float] = None
    ) -> VADResponse:
        """
        从音频字节检测

        Args:
            audio_data: 音频数据
            threshold: 阈值

        Returns:
            VAD 响应
        """
        if not self.model:
            raise RuntimeError("VAD model not loaded")

        start_time = time.time()

        # 转换音频格式
        audio_array, sample_rate = self._load_audio(audio_data)

        # 设置阈值
        threshold = threshold or settings.VAD_THRESHOLD

        # 执行 VAD
        (get_speech_timestamps, _, read_audio, *_) = self.utils

        # 检测语音时间戳
        speech_timestamps = get_speech_timestamps(
            audio_array,
            self.model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_speech_duration_ms=settings.VAD_MIN_SPEECH_DURATION_MS,
            min_silence_duration_ms=settings.VAD_MIN_SILENCE_DURATION_MS,
            speech_pad_ms=settings.VAD_SPEECH_PAD_MS,
        )

        # 转换为响应格式
        segments = []
        total_speech_duration_ms = 0.0

        for ts in speech_timestamps:
            start_ms = (ts["start"] / sample_rate) * 1000
            end_ms = (ts["end"] / sample_rate) * 1000
            duration_ms = end_ms - start_ms

            segments.append(
                VoiceSegment(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    is_speech=True,
                    confidence=None,  # Silero VAD 不提供置信度
                )
            )

            total_speech_duration_ms += duration_ms

        # 计算总时长
        total_duration_ms = (len(audio_array) / sample_rate) * 1000
        speech_ratio = total_speech_duration_ms / total_duration_ms if total_duration_ms > 0 else 0.0

        processing_time_ms = (time.time() - start_time) * 1000

        return VADResponse(
            segments=segments,
            total_speech_duration_ms=total_speech_duration_ms,
            total_duration_ms=total_duration_ms,
            speech_ratio=speech_ratio,
            processing_time_ms=processing_time_ms,
        )

    def _load_audio(self, audio_data: bytes) -> tuple:
        """
        加载音频数据并转换为 NumPy 数组

        Args:
            audio_data: 音频字节

        Returns:
            (audio_array, sample_rate)
        """
        try:
            # 使用 pydub 加载音频
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            # 转换为单声道
            if audio.channels > 1:
                audio = audio.set_channels(1)

            # 转换为 16kHz（Silero VAD 支持 8kHz 和 16kHz）
            target_sample_rate = 16000
            if audio.frame_rate != target_sample_rate:
                audio = audio.set_frame_rate(target_sample_rate)

            # 转换为 NumPy 数组
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

            # 归一化到 [-1, 1]
            samples = samples / (2**15)

            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(samples)

            return audio_tensor, target_sample_rate

        except Exception as e:
            logger.error(f"Failed to load audio: {e}", exc_info=True)
            raise

    async def _download_audio(self, url: str) -> bytes:
        """下载音频文件"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Failed to download audio from {url}: {e}")
            raise
