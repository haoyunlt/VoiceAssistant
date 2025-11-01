"""
Streaming ASR Service
WebSocket 流式语音识别服务
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AudioSegment:
    """音频段"""

    audio: np.ndarray
    start_time: float
    end_time: float


class StreamingASRService:
    """流式 ASR 服务"""

    def __init__(self, whisper_model, vad_model):
        self.whisper_model = whisper_model
        self.vad_model = vad_model
        self.min_chunk_size = 16000 * 2  # 2秒音频 (16kHz)
        self.sample_rate = 16000
        self.vad_threshold = 0.5

    def detect_speech(self, audio_bytes: bytes) -> list[AudioSegment]:
        """
        使用 VAD 检测语音段

        Args:
            audio_bytes: 音频字节数据

        Returns:
            List[AudioSegment]: 检测到的语音段列表
        """
        try:
            # 转换为 numpy 数组
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # VAD 检测
            speech_timestamps = self.vad_model(
                audio_np, self.sample_rate, threshold=self.vad_threshold
            )

            # 提取语音段
            segments = []
            for ts in speech_timestamps:
                start_sample = int(ts["start"] * self.sample_rate)
                end_sample = int(ts["end"] * self.sample_rate)
                segment_audio = audio_np[start_sample:end_sample]

                segments.append(
                    AudioSegment(audio=segment_audio, start_time=ts["start"], end_time=ts["end"])
                )

            return segments

        except Exception as e:
            logger.error(f"VAD detection failed: {e}")
            return []

    async def recognize_segment(self, segment: AudioSegment, language: str = "zh") -> dict:
        """
        识别单个语音段

        Args:
            segment: 音频段
            language: 语言代码

        Returns:
            Dict: 识别结果
        """
        try:
            # 使用 Whisper 识别
            segments, info = self.whisper_model.transcribe(
                segment.audio, language=language, beam_size=5, best_of=5, temperature=0.0
            )

            # 提取结果
            text = ""
            for seg in segments:
                text += seg.text

            # 计算置信度 (使用平均对数概率)
            confidence = (
                np.exp(info.language_probability) if hasattr(info, "language_probability") else 0.8
            )

            return {
                "text": text.strip(),
                "confidence": float(confidence),
                "language": info.language,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
            }

        except Exception as e:
            logger.error(f"ASR recognition failed: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    def merge_partial_results(self, results: list[dict]) -> str:
        """
        合并部分识别结果

        Args:
            results: 部分结果列表

        Returns:
            str: 合并后的完整文本
        """
        if not results:
            return ""

        # 按时间排序
        sorted_results = sorted(results, key=lambda x: x.get("start_time", 0))

        # 合并文本
        merged_text = " ".join([r["text"] for r in sorted_results if r.get("text")])

        return merged_text.strip()
