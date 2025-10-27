"""音频增强服务

提供多种音频增强功能:
- 均衡化(Equalization)
- 归一化(Normalization)
- 压缩(Compression)
- 增益(Gain)
- 去混响(Dereverberation)
"""
import io
import logging

import librosa
import numpy as np
import soundfile as sf
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AudioEnhancementResult(BaseModel):
    """音频增强结果"""
    audio_data: bytes
    sample_rate: int
    duration_ms: float
    enhancements_applied: list[str]


class AudioEnhancementService:
    """音频增强服务"""

    def __init__(self):
        """初始化"""
        logger.info("Audio Enhancement Service initialized")

    async def enhance(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        normalize: bool = True,
        compress: bool = False,
        equalize: bool = False,
        dereverberate: bool = False,
        gain_db: float = 0.0,
    ) -> AudioEnhancementResult:
        """
        综合音频增强

        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            normalize: 是否归一化
            compress: 是否动态范围压缩
            equalize: 是否均衡化
            dereverberate: 是否去混响
            gain_db: 增益（dB）

        Returns:
            增强结果
        """
        try:
            # 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            enhancements = []

            # 1. 去混响
            if dereverberate:
                audio = await self._dereverberate(audio, sr)
                enhancements.append("dereverberation")

            # 2. 均衡化
            if equalize:
                audio = await self._equalize(audio, sr)
                enhancements.append("equalization")

            # 3. 动态范围压缩
            if compress:
                audio = await self._compress(audio)
                enhancements.append("compression")

            # 4. 增益调整
            if gain_db != 0.0:
                audio = await self._apply_gain(audio, gain_db)
                enhancements.append(f"gain_{gain_db}dB")

            # 5. 归一化（通常最后执行）
            if normalize:
                audio = await self._normalize(audio)
                enhancements.append("normalization")

            # 转换回bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, audio, sr, format='WAV')
            output_buffer.seek(0)

            return AudioEnhancementResult(
                audio_data=output_buffer.read(),
                sample_rate=sr,
                duration_ms=len(audio) / sr * 1000,
                enhancements_applied=enhancements
            )

        except Exception as e:
            logger.error(f"Audio enhancement error: {e}", exc_info=True)
            return AudioEnhancementResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration_ms=0,
                enhancements_applied=[]
            )

    async def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """归一化音频（Peak normalization）"""
        max_val = np.abs(audio).max()
        if max_val > 0:
            return audio / max_val
        return audio

    async def _compress(self, audio: np.ndarray, threshold: float = -20.0, ratio: float = 4.0) -> np.ndarray:
        """
        动态范围压缩

        Args:
            audio: 音频数据
            threshold: 阈值（dB）
            ratio: 压缩比（4:1表示超过阈值的部分压缩到1/4）
        """
        # 转换为dB
        audio_db = librosa.amplitude_to_db(np.abs(audio))

        # 应用压缩
        compressed = audio.copy()
        mask = audio_db > threshold

        if mask.any():
            # 超过阈值的部分进行压缩
            compressed[mask] = audio[mask] * (1.0 / ratio)

        return compressed

    async def _equalize(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        频率均衡（增强人声频率范围 300Hz-3400Hz）
        """
        # 计算STFT
        stft = librosa.stft(audio)

        # 获取频率轴
        freqs = librosa.fft_frequencies(sr=sr)

        # 创建增强掩码（对300-3400Hz范围进行增强）
        voice_freq_mask = (freqs >= 300) & (freqs <= 3400)

        # 应用增强（增加1.2倍）
        stft[voice_freq_mask, :] *= 1.2

        # 反变换
        equalized_audio = librosa.istft(stft)

        return equalized_audio

    async def _dereverberate(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        去混响（简化版）
        使用维纳滤波
        """
        try:
            # 计算短时傅里叶变换
            stft = librosa.stft(audio)

            # 估计功率谱
            power_spec = np.abs(stft) ** 2

            # 估计噪声功率谱（使用前几帧）
            noise_power = power_spec[:, :10].mean(axis=1, keepdims=True)

            # 维纳滤波
            wiener_filter = power_spec / (power_spec + noise_power + 1e-10)

            # 应用滤波器
            filtered_stft = stft * wiener_filter

            # 反变换
            dereverbed_audio = librosa.istft(filtered_stft)

            return dereverbed_audio

        except Exception as e:
            logger.warning(f"Dereverberation failed: {e}, returning original")
            return audio

    async def _apply_gain(self, audio: np.ndarray, gain_db: float) -> np.ndarray:
        """
        应用增益

        Args:
            audio: 音频数据
            gain_db: 增益（dB）
        """
        # 转换dB到线性增益
        gain_linear = 10 ** (gain_db / 20.0)

        # 应用增益
        gained_audio = audio * gain_linear

        # 防止削波
        max_val = np.abs(gained_audio).max()
        if max_val > 1.0:
            gained_audio = gained_audio / max_val

        return gained_audio

    async def normalize_loudness(
        self,
        audio_data: bytes,
        target_loudness_db: float = -23.0,
        sample_rate: int = 16000
    ) -> AudioEnhancementResult:
        """
        响度归一化（EBU R128标准）

        Args:
            audio_data: 音频数据
            target_loudness_db: 目标响度（dB LUFS，默认-23符合广播标准）
            sample_rate: 采样率
        """
        try:
            import pyloudnorm as pyln

            # 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            # 创建响度计
            meter = pyln.Meter(sr)

            # 测量当前响度
            loudness = meter.integrated_loudness(audio)

            # 归一化到目标响度
            normalized_audio = pyln.normalize.loudness(audio, loudness, target_loudness_db)

            # 转换回bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, normalized_audio, sr, format='WAV')
            output_buffer.seek(0)

            return AudioEnhancementResult(
                audio_data=output_buffer.read(),
                sample_rate=sr,
                duration_ms=len(normalized_audio) / sr * 1000,
                enhancements_applied=["loudness_normalization"]
            )

        except ImportError:
            logger.warning("pyloudnorm not installed, using simple normalization")
            return await self.enhance(audio_data, sample_rate, normalize=True)
        except Exception as e:
            logger.error(f"Loudness normalization error: {e}")
            return AudioEnhancementResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration_ms=0,
                enhancements_applied=[]
            )

    async def remove_silence(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        top_db: int = 30
    ) -> AudioEnhancementResult:
        """
        移除静音段

        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            top_db: 静音阈值（dB）
        """
        try:
            # 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            # 移除静音
            trimmed_audio, _ = librosa.effects.trim(audio, top_db=top_db)

            # 转换回bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, trimmed_audio, sr, format='WAV')
            output_buffer.seek(0)

            return AudioEnhancementResult(
                audio_data=output_buffer.read(),
                sample_rate=sr,
                duration_ms=len(trimmed_audio) / sr * 1000,
                enhancements_applied=["silence_removal"]
            )

        except Exception as e:
            logger.error(f"Silence removal error: {e}")
            return AudioEnhancementResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration_ms=0,
                enhancements_applied=[]
            )

    async def health_check(self) -> dict:
        """健康检查"""
        return {
            "healthy": True,
            "service": "audio_enhancement",
            "available_enhancements": [
                "normalization",
                "compression",
                "equalization",
                "dereverberation",
                "gain",
                "loudness_normalization",
                "silence_removal"
            ]
        }
