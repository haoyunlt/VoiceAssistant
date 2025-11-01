"""
ASR (Automatic Speech Recognition) 引擎
支持 Whisper 和实时流式识别
"""

import logging
from collections.abc import Generator
from typing import Any

import numpy as np
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline

logger = logging.getLogger(__name__)


class ASREngine:
    """ASR 引擎"""

    def __init__(
        self,
        model_name: str = "openai/whisper-base",
        device: str = "auto",
        language: str = "zh",
        task: str = "transcribe",
        beam_size: int = 5,
        enable_streaming: bool = True,
    ):
        """
        初始化 ASR 引擎

        Args:
            model_name: 模型名称
            device: 设备 (cpu, cuda, auto)
            language: 语言代码
            task: 任务类型 (transcribe, translate)
            beam_size: Beam search 大小
            enable_streaming: 是否启用流式识别
        """
        self.model_name = model_name
        self.language = language
        self.task = task
        self.beam_size = beam_size
        self.enable_streaming = enable_streaming

        # 确定设备
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Loading ASR model: {model_name} on {self.device}")

        # 加载模型
        if enable_streaming:
            # 流式模式：使用 processor + model
            self.processor = WhisperProcessor.from_pretrained(model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
        else:
            # 批处理模式：使用 pipeline
            self.pipe = pipeline(
                "automatic-speech-recognition", model=model_name, device=self.device
            )

        # 音频缓冲区
        self.audio_buffer = []
        self.buffer_duration = 0.0  # 秒
        self.chunk_duration = 5.0  # 每 5 秒处理一次

        logger.info(f"ASR engine initialized: {model_name}, streaming={enable_streaming}")

    def transcribe(
        self, audio_data: bytes, sample_rate: int = 16000, return_timestamps: bool = False
    ) -> dict[str, Any]:
        """
        转录音频（批处理模式）

        Args:
            audio_data: 音频字节流
            sample_rate: 采样率
            return_timestamps: 是否返回时间戳

        Returns:
            转录结果
        """
        try:
            # 转换为 numpy 数组
            audio_array = self._bytes_to_array(audio_data, sample_rate)

            if self.enable_streaming:
                # 使用 model 直接推理
                result = self._transcribe_with_model(audio_array, sample_rate)
            else:
                # 使用 pipeline
                result = self.pipe(audio_array, return_timestamps=return_timestamps)

            logger.info(f"Transcription completed: {len(result.get('text', ''))} characters")

            return {
                "text": result.get("text", ""),
                "chunks": result.get("chunks", []),
                "language": result.get("language", self.language),
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            return {"text": "", "error": str(e)}

    def transcribe_stream(
        self, audio_stream: Generator[bytes, None, None], sample_rate: int = 16000
    ) -> Generator[dict[str, Any], None, None]:
        """
        流式转录

        Args:
            audio_stream: 音频流
            sample_rate: 采样率

        Yields:
            转录结果（增量）
        """
        logger.info("Starting streaming transcription")

        for audio_chunk in audio_stream:
            # 添加到缓冲区
            self.audio_buffer.append(audio_chunk)
            self.buffer_duration += len(audio_chunk) / sample_rate / 2  # 假设 16-bit

            # 当缓冲区达到一定长度时，进行转录
            if self.buffer_duration >= self.chunk_duration:
                # 合并缓冲区
                combined_audio = b"".join(self.audio_buffer)

                # 转录
                result = self.transcribe(combined_audio, sample_rate)

                yield {"text": result["text"], "is_final": False, "timestamp": self.buffer_duration}

                # 重置缓冲区（保留最后 1 秒用于上下文）
                overlap_duration = 1.0
                overlap_samples = int(overlap_duration * sample_rate * 2)

                if len(combined_audio) > overlap_samples:
                    self.audio_buffer = [combined_audio[-overlap_samples:]]
                    self.buffer_duration = overlap_duration
                else:
                    self.audio_buffer = []
                    self.buffer_duration = 0.0

        # 处理剩余缓冲区
        if self.audio_buffer:
            combined_audio = b"".join(self.audio_buffer)
            result = self.transcribe(combined_audio, sample_rate)

            yield {"text": result["text"], "is_final": True, "timestamp": self.buffer_duration}

    def _transcribe_with_model(self, audio_array: np.ndarray, sample_rate: int) -> dict[str, Any]:
        """使用模型直接转录"""
        # 处理音频特征
        input_features = self.processor(
            audio_array, sampling_rate=sample_rate, return_tensors="pt"
        ).input_features.to(self.device)

        # 生成转录
        with torch.no_grad():
            predicted_ids = self.model.generate(
                input_features, num_beams=self.beam_size, language=self.language, task=self.task
            )

        # 解码
        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

        return {"text": transcription, "language": self.language}

    def _bytes_to_array(self, audio_data: bytes, _sample_rate: int) -> np.ndarray:
        """将字节流转换为 numpy 数组"""
        # 假设 PCM 16-bit 格式
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # 归一化到 [-1, 1]
        audio_array = audio_array.astype(np.float32) / 32768.0
        return audio_array

    def reset(self):
        """重置缓冲区"""
        self.audio_buffer = []
        self.buffer_duration = 0.0


class VoiceActivityDetection:
    """语音活动检测（VAD）"""

    def __init__(
        self,
        model_name: str = "silero_vad",
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
    ):
        """
        初始化 VAD

        Args:
            model_name: 模型名称
            threshold: 语音阈值
            min_speech_duration_ms: 最小语音持续时间（毫秒）
            min_silence_duration_ms: 最小静音持续时间（毫秒）
        """
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms

        logger.info(f"Loading VAD model: {model_name}")

        # 加载 Silero VAD
        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", force_reload=False
        )

        self.model.eval()

        logger.info("VAD initialized")

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """
        检测音频块是否包含语音

        Args:
            audio_chunk: 音频字节
            sample_rate: 采样率

        Returns:
            是否为语音
        """
        # 转换为 tensor
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_tensor = torch.from_numpy(audio_array).float() / 32768.0

        # VAD 检测
        with torch.no_grad():
            speech_prob = self.model(audio_tensor, sample_rate).item()

        return speech_prob > self.threshold

    def detect_speech_segments(
        self, audio_data: bytes, sample_rate: int = 16000, chunk_size_ms: int = 30
    ) -> list:
        """
        检测语音段落

        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            chunk_size_ms: 块大小（毫秒）

        Returns:
            语音段列表 [(start_ms, end_ms), ...]
        """
        chunk_samples = int(sample_rate * chunk_size_ms / 1000)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        segments = []
        is_speaking = False
        speech_start = 0

        for i in range(0, len(audio_array), chunk_samples):
            chunk = audio_array[i : i + chunk_samples]
            if len(chunk) == 0:
                continue

            # 检测当前块
            chunk_bytes = chunk.tobytes()
            has_speech = self.is_speech(chunk_bytes, sample_rate)

            timestamp_ms = i / sample_rate * 1000

            if has_speech and not is_speaking:
                # 语音开始
                is_speaking = True
                speech_start = timestamp_ms
            elif not has_speech and is_speaking:
                # 语音结束
                is_speaking = False
                segments.append((speech_start, timestamp_ms))

        # 处理未结束的语音
        if is_speaking:
            end_ms = len(audio_array) / sample_rate * 1000
            segments.append((speech_start, end_ms))

        return segments
