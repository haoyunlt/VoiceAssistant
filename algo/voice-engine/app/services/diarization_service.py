"""
说话人分离服务（Speaker Diarization）

使用Pyannote-audio进行说话人分离，识别音频中的不同说话人
"""

import contextlib
import logging
import os
import tempfile

import numpy as np

logger = logging.getLogger(__name__)


class DiarizationService:
    """说话人分离服务"""

    def __init__(
        self,
        use_auth_token: str | None = None,
        device: str = "cpu",
    ):
        """
        初始化说话人分离服务

        Args:
            use_auth_token: HuggingFace token（pyannote-audio需要）
            device: 设备类型（cpu/cuda）
        """
        self.device = device
        self.pipeline = None
        self.use_auth_token = use_auth_token or os.getenv("HF_TOKEN")

        # 延迟加载模型
        self._load_pipeline()

    def _load_pipeline(self):
        """加载Pyannote pipeline"""
        try:
            from pyannote.audio import Pipeline

            if self.use_auth_token:
                # 使用预训练模型
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=self.use_auth_token,
                )

                # 设置设备
                if self.device == "cuda":
                    import torch
                    if torch.cuda.is_available():
                        self.pipeline = self.pipeline.to(torch.device("cuda"))
                    else:
                        logger.warning("CUDA不可用，使用CPU")
                        self.device = "cpu"

                logger.info(f"Pyannote pipeline加载成功 (device: {self.device})")
            else:
                logger.warning("未提供HF_TOKEN，无法加载Pyannote模型")
                self.pipeline = None

        except ImportError:
            logger.warning("pyannote.audio未安装，说话人分离功能不可用")
            self.pipeline = None
        except Exception as e:
            logger.error(f"加载Pyannote pipeline失败: {e}")
            self.pipeline = None

    def diarize(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict:
        """
        执行说话人分离

        Args:
            audio_data: 音频数据（字节流）
            sample_rate: 采样率
            min_speakers: 最小说话人数
            max_speakers: 最大说话人数

        Returns:
            Dict包含：
            - segments: 分段信息列表
            - speakers: 说话人列表
            - total_speakers: 总说话人数
            - duration: 音频时长
        """
        if self.pipeline is None:
            return self._mock_diarization(audio_data, sample_rate)

        try:
            # 将音频数据保存为临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                self._save_audio(audio_data, temp_path, sample_rate)

            # 执行说话人分离
            diarization_kwargs = {}
            if min_speakers is not None:
                diarization_kwargs["min_speakers"] = min_speakers
            if max_speakers is not None:
                diarization_kwargs["max_speakers"] = max_speakers

            diarization = self.pipeline(temp_path, **diarization_kwargs)

            # 解析结果
            segments = []
            speakers = set()

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segment = {
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "duration": float(turn.end - turn.start),
                    "speaker": speaker,
                }
                segments.append(segment)
                speakers.add(speaker)

            # 清理临时文件
            with contextlib.suppress(Exception):
                os.unlink(temp_path)

            # 计算音频时长
            duration = max([seg["end"] for seg in segments]) if segments else 0.0

            # 按时间排序
            segments.sort(key=lambda x: x["start"])

            result = {
                "segments": segments,
                "speakers": sorted(speakers),
                "total_speakers": len(speakers),
                "duration": duration,
            }

            logger.info(
                f"说话人分离完成: {len(segments)}个片段, {len(speakers)}位说话人"
            )

            return result

        except Exception as e:
            logger.error(f"说话人分离失败: {e}", exc_info=True)
            return {
                "segments": [],
                "speakers": [],
                "total_speakers": 0,
                "duration": 0.0,
                "error": str(e),
            }

    def _save_audio(self, audio_data: bytes, output_path: str, sample_rate: int):
        """保存音频到文件"""
        import wave

        # 转换为numpy数组
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # 保存为WAV文件
        with wave.open(output_path, "wb") as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())

    def _mock_diarization(self, audio_data: bytes, sample_rate: int) -> dict:
        """
        模拟说话人分离（当Pyannote不可用时）

        使用简单的能量检测和固定时间窗口
        """
        logger.info("使用Mock说话人分离")

        # 转换音频数据
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        audio_array = audio_array / 32768.0

        # 计算音频时长
        duration = len(audio_array) / sample_rate

        # 简单分段：每5秒切换说话人
        segments = []
        segment_duration = 5.0
        num_segments = int(duration / segment_duration) + 1

        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)

            if end - start < 0.1:  # 跳过过短的片段
                continue

            # 交替分配说话人
            speaker = f"SPEAKER_{i % 2}"

            segments.append({
                "start": start,
                "end": end,
                "duration": end - start,
                "speaker": speaker,
            })

        speakers = list({seg["speaker"] for seg in segments})

        return {
            "segments": segments,
            "speakers": sorted(speakers),
            "total_speakers": len(speakers),
            "duration": duration,
            "mock": True,
        }

    def diarize_from_file(self, audio_path: str) -> dict:
        """
        从文件执行说话人分离

        Args:
            audio_path: 音频文件路径

        Returns:
            分离结果
        """
        try:
            import librosa

            # 加载音频
            audio_array, sr = librosa.load(audio_path, sr=16000)

            # 转换为字节流
            audio_int16 = (audio_array * 32768).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            return self.diarize(audio_bytes, sr)

        except Exception as e:
            logger.error(f"从文件执行说话人分离失败: {e}", exc_info=True)
            return {
                "segments": [],
                "speakers": [],
                "total_speakers": 0,
                "duration": 0.0,
                "error": str(e),
            }

    def get_speaker_timeline(self, diarization_result: dict) -> dict[str, list[tuple]]:
        """
        获取每个说话人的时间线

        Args:
            diarization_result: 分离结果

        Returns:
            Dict[speaker_id, List[(start, end)]]
        """
        timeline = {}

        for segment in diarization_result.get("segments", []):
            speaker = segment["speaker"]
            if speaker not in timeline:
                timeline[speaker] = []
            timeline[speaker].append((segment["start"], segment["end"]))

        return timeline

    def calculate_speaking_time(self, diarization_result: dict) -> dict[str, float]:
        """
        计算每个说话人的发言时长

        Args:
            diarization_result: 分离结果

        Returns:
            Dict[speaker_id, total_duration]
        """
        speaking_time = {}

        for segment in diarization_result.get("segments", []):
            speaker = segment["speaker"]
            duration = segment["duration"]

            if speaker not in speaking_time:
                speaking_time[speaker] = 0.0
            speaking_time[speaker] += duration

        return speaking_time

    def get_speaker_statistics(self, diarization_result: dict) -> dict:
        """
        获取说话人统计信息

        Args:
            diarization_result: 分离结果

        Returns:
            统计信息字典
        """
        speaking_time = self.calculate_speaking_time(diarization_result)
        total_duration = diarization_result.get("duration", 0.0)

        statistics = {
            "total_duration": total_duration,
            "total_speakers": diarization_result.get("total_speakers", 0),
            "speakers": {},
        }

        for speaker, duration in speaking_time.items():
            percentage = (duration / total_duration * 100) if total_duration > 0 else 0

            statistics["speakers"][speaker] = {
                "speaking_time": duration,
                "percentage": round(percentage, 2),
                "segment_count": len([
                    s for s in diarization_result.get("segments", [])
                    if s["speaker"] == speaker
                ]),
            }

        return statistics


# 全局单例
_diarization_service: DiarizationService | None = None


def get_diarization_service() -> DiarizationService:
    """获取说话人分离服务单例"""
    global _diarization_service
    if _diarization_service is None:
        _diarization_service = DiarizationService()
    return _diarization_service
