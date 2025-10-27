"""
ASR (Automatic Speech Recognition) service
"""

import base64
import io
import os
import time
from typing import Optional

import httpx
import torch
from faster_whisper import WhisperModel

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.voice import ASRRequest, ASRResponse
from app.services.vad_service import VADService

logger = get_logger(__name__)


class ASRService:
    """ASR 识别服务"""

    def __init__(self):
        self.provider = settings.ASR_PROVIDER
        self.model = None
        self.vad_service = VADService()
        self.azure_service = None

        if self.provider == "whisper":
            self._load_whisper_model()
        elif self.provider == "azure":
            self._initialize_azure()

    def _initialize_azure(self):
        """初始化Azure Speech Service"""
        try:
            from app.services.azure_speech_service import AzureSpeechService

            subscription_key = os.getenv("AZURE_SPEECH_KEY")
            region = os.getenv("AZURE_SPEECH_REGION", "eastus")

            if not subscription_key:
                logger.warning("AZURE_SPEECH_KEY not set, Azure ASR will not be available")
                return

            self.azure_service = AzureSpeechService(
                subscription_key=subscription_key,
                region=region
            )

            logger.info("Azure Speech Service initialized for ASR")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Speech Service: {e}")

    def _load_whisper_model(self):
        """加载 Whisper 模型"""
        try:
            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            logger.info(
                f"Loading Whisper model: {settings.WHISPER_MODEL}, "
                f"device={device}, compute_type={compute_type}"
            )

            self.model = WhisperModel(
                settings.WHISPER_MODEL,
                device=device,
                compute_type=compute_type,
            )

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            # 不抛出异常，允许服务启动（降级模式）

    async def recognize(self, request: ASRRequest) -> ASRResponse:
        """
        语音识别

        Args:
            request: ASR 请求

        Returns:
            ASR 响应
        """
        start_time = time.time()

        # 获取音频数据
        if request.audio_base64:
            audio_data = base64.b64decode(request.audio_base64)
        elif request.audio_url:
            audio_data = await self._download_audio(request.audio_url)
        else:
            raise ValueError("Either audio_url or audio_base64 must be provided")

        # 识别
        response = await self.recognize_from_bytes(
            audio_data=audio_data,
            language=request.language,
            enable_vad=request.enable_vad,
            task=request.task,
        )

        return response

    async def recognize_from_bytes(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        enable_vad: bool = True,
        task: str = "transcribe",
    ) -> ASRResponse:
        """
        从音频字节识别

        Args:
            audio_data: 音频数据
            language: 语言代码
            enable_vad: 是否启用 VAD
            task: 任务类型

        Returns:
            ASR 响应
        """
        start_time = time.time()

        # VAD 预处理（可选）
        if enable_vad:
            vad_result = await self.vad_service.detect_from_bytes(audio_data)
            if vad_result.speech_ratio < 0.1:
                # 几乎没有语音内容
                logger.warning(f"Low speech ratio: {vad_result.speech_ratio:.2%}")

        # 根据 provider 选择识别方式
        if self.provider == "whisper":
            result = await self._recognize_with_whisper(audio_data, language, task)
        elif self.provider == "azure":
            result = await self._recognize_with_azure(audio_data, language)
        else:
            raise ValueError(f"Unsupported ASR provider: {self.provider}")

        processing_time_ms = (time.time() - start_time) * 1000

        return ASRResponse(
            text=result["text"],
            language=result["language"],
            confidence=result.get("confidence"),
            segments=result.get("segments"),
            duration_ms=result.get("duration_ms", 0),
            processing_time_ms=processing_time_ms,
        )

    async def _recognize_with_whisper(
        self, audio_data: bytes, language: Optional[str], task: str
    ) -> dict:
        """使用 Whisper 模型识别"""
        if not self.model:
            raise RuntimeError("Whisper model not loaded")

        try:
            # 将音频数据写入临时文件或使用内存流
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()

                # 执行识别
                segments, info = self.model.transcribe(
                    temp_file.name,
                    language=language,
                    task=task,
                    vad_filter=True,
                    vad_parameters=dict(
                        threshold=settings.VAD_THRESHOLD,
                        min_speech_duration_ms=settings.VAD_MIN_SPEECH_DURATION_MS,
                        min_silence_duration_ms=settings.VAD_MIN_SILENCE_DURATION_MS,
                    ),
                )

                # 提取结果
                text_segments = []
                full_text = []

                for segment in segments:
                    text_segments.append(
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text.strip(),
                        }
                    )
                    full_text.append(segment.text.strip())

                result = {
                    "text": " ".join(full_text),
                    "language": info.language,
                    "segments": text_segments,
                    "duration_ms": info.duration * 1000,
                }

                return result

        except Exception as e:
            logger.error(f"Whisper recognition failed: {e}", exc_info=True)
            raise

    async def _recognize_with_azure(self, audio_data: bytes, language: Optional[str]) -> dict:
        """使用 Azure Speech 识别"""
        if not self.azure_service:
            raise RuntimeError("Azure Speech Service not initialized")

        try:
            # 确保Azure服务已初始化
            if not self.azure_service.initialized:
                await self.azure_service.initialize()

            lang = language or "zh-CN"

            # 调用Azure Speech SDK
            result = await self.azure_service.recognize_from_bytes(
                audio_data=audio_data,
                language=lang
            )

            if not result.get("success"):
                raise Exception(result.get("error", "Unknown error"))

            return {
                "text": result["text"],
                "language": result["language"],
                "confidence": result.get("confidence", 0.95),
                "duration_ms": result.get("duration", 0),
            }

        except Exception as e:
            logger.error(f"Azure ASR recognition failed: {e}", exc_info=True)
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
