"""噪音抑制服务"""
import io

import librosa
import noisereduce as nr
import soundfile as sf
from pydantic import BaseModel

from app.core.logging import logger


class NoiseSuppressionResult(BaseModel):
    """降噪结果"""
    audio_data: bytes
    sample_rate: int
    original_duration_ms: float
    noise_reduced: bool


class NoiseSuppressionService:
    """噪音抑制服务"""

    def __init__(self):
        """初始化"""
        # 默认参数
        self.default_prop_decrease = 1.0  # 噪音减少程度（0-1）
        self.default_time_mask_smooth_ms = 50  # 时间掩码平滑（毫秒）
        self.default_freq_mask_smooth_hz = 500  # 频率掩码平滑（Hz）

        logger.info("Noise suppression service initialized")

    async def reduce_noise(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        stationary: bool = True,
        prop_decrease: float = None,
        time_mask_smooth_ms: int = None,
        freq_mask_smooth_hz: int = None
    ) -> NoiseSuppressionResult:
        """降噪处理

        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            stationary: 是否为平稳噪音（如风扇、空调）
            prop_decrease: 噪音减少程度（0-1）
            time_mask_smooth_ms: 时间掩码平滑
            freq_mask_smooth_hz: 频率掩码平滑

        Returns:
            降噪结果
        """
        try:
            # 1. 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            original_duration_ms = len(audio) / sr * 1000

            # 2. 设置参数
            if prop_decrease is None:
                prop_decrease = self.default_prop_decrease
            if time_mask_smooth_ms is None:
                time_mask_smooth_ms = self.default_time_mask_smooth_ms
            if freq_mask_smooth_hz is None:
                freq_mask_smooth_hz = self.default_freq_mask_smooth_hz

            # 3. 降噪
            if stationary:
                # 平稳噪音（如风扇、空调）
                reduced_audio = nr.reduce_noise(
                    y=audio,
                    sr=sr,
                    stationary=True,
                    prop_decrease=prop_decrease,
                    time_mask_smooth_ms=time_mask_smooth_ms,
                    freq_mask_smooth_hz=freq_mask_smooth_hz
                )
            else:
                # 非平稳噪音（如突发声音）
                reduced_audio = nr.reduce_noise(
                    y=audio,
                    sr=sr,
                    stationary=False,
                    prop_decrease=prop_decrease,
                    use_torch=True  # 使用PyTorch加速
                )

            # 4. 转换回bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, reduced_audio, sr, format='WAV')
            output_buffer.seek(0)
            reduced_audio_data = output_buffer.read()

            return NoiseSuppressionResult(
                audio_data=reduced_audio_data,
                sample_rate=sr,
                original_duration_ms=original_duration_ms,
                noise_reduced=True
            )
        except Exception as e:
            logger.error(f"Noise suppression error: {e}")
            # 失败时返回原始音频
            return NoiseSuppressionResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                original_duration_ms=len(audio) / sample_rate * 1000 if 'audio' in locals() else 0,
                noise_reduced=False
            )

    async def adaptive_reduce_noise(
        self,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> NoiseSuppressionResult:
        """自适应降噪（自动检测噪音类型）

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            降噪结果
        """
        try:
            # 1. 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            # 2. 分析音频特征，判断噪音类型
            stationary = await self._detect_noise_type(audio, sr)

            # 3. 根据检测结果降噪
            return await self.reduce_noise(
                audio_data,
                sample_rate=sample_rate,
                stationary=stationary
            )
        except Exception as e:
            logger.error(f"Adaptive noise suppression error: {e}")
            return NoiseSuppressionResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                original_duration_ms=0,
                noise_reduced=False
            )

    async def _detect_noise_type(self, audio: any, sr: int) -> bool:
        """检测噪音类型

        Args:
            audio: 音频数组
            sr: 采样率

        Returns:
            是否为平稳噪音
        """
        try:
            # 计算短时能量
            frame_length = int(0.025 * sr)  # 25ms
            hop_length = int(0.010 * sr)    # 10ms

            # 计算能量
            energy = librosa.feature.rms(
                y=audio,
                frame_length=frame_length,
                hop_length=hop_length
            )[0]

            # 计算能量方差
            energy_variance = energy.var()

            # 如果能量方差小，说明是平稳噪音
            # 阈值可以根据实际情况调整
            stationary_threshold = 0.01

            return energy_variance < stationary_threshold
        except Exception as e:
            logger.warning(f"Noise type detection error: {e}, defaulting to stationary")
            return True

    async def reduce_noise_with_profile(
        self,
        audio_data: bytes,
        noise_profile_data: bytes,
        sample_rate: int = 16000
    ) -> NoiseSuppressionResult:
        """使用噪音配置文件降噪

        Args:
            audio_data: 音频数据
            noise_profile_data: 噪音配置文件（纯噪音样本）
            sample_rate: 采样率

        Returns:
            降噪结果
        """
        try:
            # 1. 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            # 2. 加载噪音配置文件
            noise_profile, _ = librosa.load(
                io.BytesIO(noise_profile_data),
                sr=sample_rate,
                mono=True
            )

            # 3. 使用噪音配置文件降噪
            reduced_audio = nr.reduce_noise(
                y=audio,
                sr=sr,
                y_noise=noise_profile,
                stationary=True,
                prop_decrease=1.0
            )

            # 4. 转换回bytes
            output_buffer = io.BytesIO()
            sf.write(output_buffer, reduced_audio, sr, format='WAV')
            output_buffer.seek(0)

            return NoiseSuppressionResult(
                audio_data=output_buffer.read(),
                sample_rate=sr,
                original_duration_ms=len(audio) / sr * 1000,
                noise_reduced=True
            )
        except Exception as e:
            logger.error(f"Profile-based noise suppression error: {e}")
            return NoiseSuppressionResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                original_duration_ms=0,
                noise_reduced=False
            )
