"""
VAD Engine - 语音活动检测引擎（Silero-VAD）
"""

import io
import logging

import numpy as np

logger = logging.getLogger(__name__)


class VADEngine:
    """VAD 引擎（基于 Silero-VAD）"""

    def __init__(self):
        """初始化 VAD 引擎"""
        self.model = None
        self.sample_rate = 16000
        logger.info("VAD engine created")

    async def initialize(self):
        """初始化 Silero-VAD 模型"""
        try:
            import torch

            # 加载 Silero-VAD 模型
            self.model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
            )

            logger.info("Silero-VAD model loaded successfully")

        except Exception as e:
            logger.warning(f"Silero-VAD not available: {e}. Using mock implementation.")
            self.model = None

    async def detect(
        self,
        audio_data: bytes,
        threshold: float = 0.5,
    ) -> list[dict]:
        """
        检测语音活动

        Args:
            audio_data: 音频数据
            threshold: 检测阈值

        Returns:
            语音片段列表
        """
        if self.model is None:
            # Mock 实现
            return self._mock_detect(audio_data)

        try:
            # 将音频数据转换为 numpy 数组
            audio_array = self._load_audio(audio_data)

            # 执行 VAD
            speech_timestamps = self._get_speech_timestamps(
                audio_array,
                threshold=threshold,
            )

            return speech_timestamps

        except Exception as e:
            logger.error(f"VAD detection failed: {e}", exc_info=True)
            raise

    def _load_audio(self, audio_data: bytes) -> np.ndarray:
        """加载音频数据"""
        try:
            import soundfile as sf

            # 从字节流读取音频
            audio_file = io.BytesIO(audio_data)
            audio_array, sr = sf.read(audio_file)

            # 重采样到 16kHz（如果需要）
            if sr != self.sample_rate:
                from scipy import signal

                num_samples = int(len(audio_array) * self.sample_rate / sr)
                audio_array = signal.resample(audio_array, num_samples)

            # 转换为单声道
            if len(audio_array.shape) > 1:
                audio_array = audio_array.mean(axis=1)

            return audio_array.astype(np.float32)

        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            # 返回空数组
            return np.array([], dtype=np.float32)

    def _get_speech_timestamps(
        self,
        audio: np.ndarray,
        threshold: float = 0.5,
    ) -> list[dict]:
        """获取语音时间戳"""
        try:
            import torch

            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(audio)

            # 执行 VAD
            speech_timestamps = []
            window_size = 512
            step_size = 256

            for i in range(0, len(audio) - window_size, step_size):
                window = audio_tensor[i : i + window_size]
                speech_prob = self.model(window, self.sample_rate).item()

                if speech_prob > threshold:
                    start_time = i / self.sample_rate
                    end_time = (i + window_size) / self.sample_rate

                    speech_timestamps.append({
                        "start": start_time,
                        "end": end_time,
                        "confidence": speech_prob,
                    })

            # 合并连续的语音片段
            merged = self._merge_segments(speech_timestamps)

            return merged

        except Exception as e:
            logger.error(f"Failed to get speech timestamps: {e}")
            return []

    def _merge_segments(self, segments: list[dict], gap_threshold: float = 0.3) -> list[dict]:
        """合并连续的语音片段"""
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for next_seg in segments[1:]:
            # 如果间隔小于阈值，合并
            if next_seg["start"] - current["end"] < gap_threshold:
                current["end"] = next_seg["end"]
                current["confidence"] = max(current["confidence"], next_seg["confidence"])
            else:
                merged.append(current)
                current = next_seg.copy()

        merged.append(current)

        return merged

    def _mock_detect(self, audio_data: bytes) -> list[dict]:
        """Mock 检测（用于测试）"""
        return [
            {
                "start": 0.0,
                "end": 2.0,
                "confidence": 0.95,
            },
            {
                "start": 3.0,
                "end": 5.0,
                "confidence": 0.88,
            },
        ]

    async def cleanup(self):
        """清理资源"""
        if self.model:
            del self.model
            self.model = None
        logger.info("VAD engine cleaned up")
