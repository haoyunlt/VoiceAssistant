"""
流式 ASR 服务

实现实时语音识别，支持:
- WebRTC VAD 端点检测
- 增量识别 (快速返回中间结果)
- 最终识别 (高准确率)
- 语音活动检测与静音处理
"""

import asyncio
import time
from typing import AsyncIterator, Dict, Optional

import numpy as np

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class StreamingASRService:
    """流式 ASR 服务"""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "zh",
        vad_enabled: bool = True,
        chunk_duration_ms: int = 300,
        vad_mode: int = 3,
        max_silence_duration_ms: int = 1500,
        partial_recognition_interval_s: int = 3,
    ):
        """
        初始化流式 ASR 服务

        Args:
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
            language: 语言代码 (zh, en, etc.)
            vad_enabled: 是否启用 VAD
            chunk_duration_ms: 音频块时长 (毫秒)
            vad_mode: VAD 模式 (0-3, 3 最严格)
            max_silence_duration_ms: 最大静音时长,超过则触发最终识别
            partial_recognition_interval_s: 增量识别间隔 (秒)
        """
        self.model_size = model_size
        self.language = language
        self.vad_enabled = vad_enabled
        self.chunk_duration_ms = chunk_duration_ms
        self.vad_mode = vad_mode
        self.max_silence_duration_ms = max_silence_duration_ms
        self.partial_recognition_interval_s = partial_recognition_interval_s

        # 音频参数
        self.sample_rate = 16000
        self.chunk_size = int(self.sample_rate * chunk_duration_ms / 1000)

        # 状态管理
        self.audio_buffer = bytearray()
        self.speech_buffer = bytearray()
        self.is_speaking = False
        self.silence_duration = 0

        # 懒加载模型
        self._whisper_model = None
        self._vad = None

        logger.info(
            f"StreamingASRService initialized: model_size={model_size}, "
            f"language={language}, vad_enabled={vad_enabled}"
        )

    def _init_whisper_model(self):
        """懒加载 Whisper 模型"""
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel

                logger.info(f"Loading Whisper model: {self.model_size}")
                self._whisper_model = WhisperModel(
                    self.model_size, device="cpu", compute_type="int8"
                )
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
                raise

    def _init_vad(self):
        """懒加载 VAD"""
        if self._vad is None and self.vad_enabled:
            try:
                import webrtcvad

                self._vad = webrtcvad.Vad(self.vad_mode)
                logger.info(f"WebRTC VAD initialized: mode={self.vad_mode}")
            except Exception as e:
                logger.warning(f"Failed to initialize VAD: {e}. Disabling VAD.")
                self.vad_enabled = False

    async def process_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[Dict]:
        """
        处理音频流，返回识别结果流

        Args:
            audio_stream: 音频数据流 (PCM, 16kHz, 16-bit, mono)

        Yields:
            识别结果字典:
            - session_start: 会话开始
            - speech_start: 语音开始
            - partial_result: 增量识别结果
            - final_result: 最终识别结果
            - speech_end: 语音结束
            - session_end: 会话结束
        """
        # 初始化模型
        self._init_whisper_model()
        self._init_vad()

        # 会话开始
        yield {
            "type": "session_start",
            "sample_rate": self.sample_rate,
            "chunk_duration_ms": self.chunk_duration_ms,
            "vad_enabled": self.vad_enabled,
            "timestamp": time.time(),
        }

        # 处理音频流
        try:
            async for audio_chunk in audio_stream:
                # 添加到缓冲区
                self.audio_buffer.extend(audio_chunk)

                # 处理完整的 chunk
                while len(self.audio_buffer) >= self.chunk_size * 2:  # 16-bit = 2 bytes
                    chunk = bytes(self.audio_buffer[: self.chunk_size * 2])
                    self.audio_buffer = self.audio_buffer[self.chunk_size * 2 :]

                    # VAD 检测
                    is_speech = self._detect_speech(chunk)

                    if is_speech:
                        # 检测到语音
                        if not self.is_speaking:
                            # 语音开始
                            self.is_speaking = True
                            self.speech_buffer = bytearray()
                            self.silence_duration = 0

                            yield {
                                "type": "speech_start",
                                "timestamp": time.time(),
                            }
                            logger.debug("Speech started")

                        # 累积语音数据
                        self.speech_buffer.extend(chunk)
                        self.silence_duration = 0

                        # 增量识别 (每隔 N 秒)
                        speech_duration_s = (
                            len(self.speech_buffer) / self.sample_rate / 2
                        )
                        if (
                            speech_duration_s
                            >= self.partial_recognition_interval_s
                        ):
                            partial_text = await self._recognize_partial(
                                self.speech_buffer
                            )

                            if partial_text:
                                yield {
                                    "type": "partial_result",
                                    "text": partial_text,
                                    "is_final": False,
                                    "timestamp": time.time(),
                                }
                                logger.debug(f"Partial result: {partial_text[:50]}...")

                    else:
                        # 静音
                        if self.is_speaking:
                            self.silence_duration += self.chunk_duration_ms
                            self.speech_buffer.extend(
                                chunk
                            )  # 保留静音以保持连贯性

                            # 静音超过阈值，触发最终识别
                            if (
                                self.silence_duration
                                >= self.max_silence_duration_ms
                            ):
                                final_text, confidence = await self._recognize_final(
                                    self.speech_buffer
                                )

                                duration_ms = (
                                    len(self.speech_buffer)
                                    / self.sample_rate
                                    / 2
                                    * 1000
                                )

                                yield {
                                    "type": "final_result",
                                    "text": final_text,
                                    "is_final": True,
                                    "confidence": confidence,
                                    "duration_ms": duration_ms,
                                    "timestamp": time.time(),
                                }
                                logger.info(
                                    f"Final result: {final_text} (confidence: {confidence:.2f})"
                                )

                                # 重置状态
                                self.is_speaking = False
                                self.speech_buffer = bytearray()
                                self.silence_duration = 0

                                yield {
                                    "type": "speech_end",
                                    "timestamp": time.time(),
                                }
                                logger.debug("Speech ended")

            # 流结束，处理剩余数据
            if self.is_speaking and len(self.speech_buffer) > 0:
                logger.info("Processing remaining speech data")
                final_text, confidence = await self._recognize_final(
                    self.speech_buffer
                )

                duration_ms = len(self.speech_buffer) / self.sample_rate / 2 * 1000

                yield {
                    "type": "final_result",
                    "text": final_text,
                    "is_final": True,
                    "confidence": confidence,
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                }

                yield {
                    "type": "speech_end",
                    "timestamp": time.time(),
                }

        except Exception as e:
            logger.error(f"Error processing audio stream: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": time.time(),
            }

        # 会话结束
        yield {
            "type": "session_end",
            "timestamp": time.time(),
        }
        logger.info("Streaming ASR session ended")

    def _detect_speech(self, audio_chunk: bytes) -> bool:
        """
        VAD 检测是否为语音

        Args:
            audio_chunk: 音频块 (固定大小)

        Returns:
            是否为语音
        """
        if not self.vad_enabled or self._vad is None:
            return True  # VAD 未启用，默认为语音

        try:
            # WebRTC VAD 要求特定的音频块大小
            # 支持的大小: 10ms, 20ms, 30ms at 8kHz, 16kHz, 32kHz, 48kHz
            # 我们使用 16kHz, 所以块大小应该是 320 (20ms) 或 480 (30ms) 字节
            return self._vad.is_speech(audio_chunk, self.sample_rate)

        except Exception as e:
            logger.warning(f"VAD detection failed: {e}")
            return True  # 失败时默认为语音

    async def _recognize_partial(self, audio_data: bytes) -> str:
        """
        增量识别 (快速，准确率较低)

        使用较小的 beam_size 和 best_of 加速识别

        Args:
            audio_data: 音频数据 (PCM)

        Returns:
            识别文本
        """
        try:
            audio_array = self._bytes_to_float32(audio_data)

            # 使用异步方式避免阻塞
            loop = asyncio.get_event_loop()
            segments, _ = await loop.run_in_executor(
                None,
                lambda: self._whisper_model.transcribe(
                    audio_array,
                    language=self.language,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=False,
                    condition_on_previous_text=False,
                ),
            )

            text = " ".join([seg.text for seg in segments])
            return text.strip()

        except Exception as e:
            logger.error(f"Partial recognition failed: {e}", exc_info=True)
            return ""

    async def _recognize_final(self, audio_data: bytes) -> tuple[str, float]:
        """
        最终识别 (完整准确率)

        使用更大的 beam_size 和 best_of 提高准确率

        Args:
            audio_data: 音频数据 (PCM)

        Returns:
            (识别文本, 平均置信度)
        """
        try:
            audio_array = self._bytes_to_float32(audio_data)

            # 使用异步方式避免阻塞
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self._whisper_model.transcribe(
                    audio_array,
                    language=self.language,
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    vad_filter=True,
                    condition_on_previous_text=True,
                ),
            )

            # 收集所有 segments
            text_segments = list(segments)
            text = " ".join([seg.text for seg in text_segments])

            # 计算平均置信度
            if text_segments:
                avg_confidence = np.mean(
                    [np.exp(seg.avg_logprob) for seg in text_segments]
                )
            else:
                avg_confidence = 0.0

            return text.strip(), float(avg_confidence)

        except Exception as e:
            logger.error(f"Final recognition failed: {e}", exc_info=True)
            return "", 0.0

    def _bytes_to_float32(self, audio_bytes: bytes) -> np.ndarray:
        """
        字节转音频数组

        Args:
            audio_bytes: PCM 音频字节 (16-bit, little-endian)

        Returns:
            Float32 音频数组 (归一化到 [-1.0, 1.0])
        """
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        return audio_float32
