"""说话人分离服务"""
import io
import os
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import torch
from pyannote.audio import Pipeline
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.services.asr_service import ASRService
from app.utils.audio import extract_audio_segment


@dataclass
class SpeakerSegment:
    """说话人片段"""
    start_ms: float
    end_ms: float
    speaker_id: str
    duration_ms: float


class DiarizationResult(BaseModel):
    """说话人分离结果"""
    segments: List[SpeakerSegment]
    num_speakers: int


class SpeakerTranscript(BaseModel):
    """带说话人的转写结果"""
    speaker_id: str
    start_ms: float
    end_ms: float
    text: str
    confidence: float


class TranscriptWithSpeakers(BaseModel):
    """完整的说话人转写"""
    transcripts: List[SpeakerTranscript]
    num_speakers: int


class SpeakerDiarizationService:
    """说话人分离服务"""

    def __init__(self, asr_service: Optional[ASRService] = None):
        """初始化

        Args:
            asr_service: ASR服务，用于转写
        """
        self.asr_service = asr_service
        self.pipeline = None
        self._load_model()

    def _load_model(self):
        """加载说话人分离模型"""
        try:
            # 加载pyannote.audio预训练模型
            # 需要HuggingFace Token: https://huggingface.co/pyannote/speaker-diarization
            hf_token = settings.get("HUGGINGFACE_TOKEN", "")

            if not hf_token:
                logger.warning("HUGGINGFACE_TOKEN not set, speaker diarization will not work")
                return

            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )

            # 使用GPU（如果可用）
            if torch.cuda.is_available():
                self.pipeline.to(torch.device("cuda"))

            logger.info("Speaker diarization model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load speaker diarization model: {e}")

    async def diarize(
        self,
        audio_data: bytes,
        num_speakers: Optional[int] = None,
        min_speakers: int = 1,
        max_speakers: int = 10
    ) -> DiarizationResult:
        """说话人分离

        Args:
            audio_data: 音频数据
            num_speakers: 说话人数量（如果已知）
            min_speakers: 最小说话人数
            max_speakers: 最大说话人数

        Returns:
            说话人分离结果
        """
        if not self.pipeline:
            raise RuntimeError("Speaker diarization model not loaded")

        # 1. 保存临时音频文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_data)

        try:
            # 2. 执行说话人分离
            if num_speakers:
                diarization = self.pipeline(
                    temp_path,
                    num_speakers=num_speakers
                )
            else:
                diarization = self.pipeline(
                    temp_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )

            # 3. 解析结果
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(SpeakerSegment(
                    start_ms=turn.start * 1000,
                    end_ms=turn.end * 1000,
                    speaker_id=speaker,
                    duration_ms=(turn.end - turn.start) * 1000
                ))

            # 按时间排序
            segments.sort(key=lambda x: x.start_ms)

            return DiarizationResult(
                segments=segments,
                num_speakers=len(set(seg.speaker_id for seg in segments))
            )
        finally:
            # 4. 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def diarize_and_transcribe(
        self,
        audio_data: bytes,
        language: str = "zh",
        num_speakers: Optional[int] = None
    ) -> TranscriptWithSpeakers:
        """说话人分离 + 语音识别

        Args:
            audio_data: 音频数据
            language: 语言代码
            num_speakers: 说话人数量

        Returns:
            带说话人的转写结果
        """
        if not self.asr_service:
            raise RuntimeError("ASR service not initialized")

        # 1. 说话人分离
        diarization_result = await self.diarize(
            audio_data=audio_data,
            num_speakers=num_speakers
        )

        # 2. 为每个片段识别
        transcripts = []

        for segment in diarization_result.segments:
            try:
                # 提取片段音频
                segment_audio = extract_audio_segment(
                    audio_data,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms
                )

                # ASR识别
                asr_result = await self.asr_service.recognize_from_bytes(
                    audio_bytes=segment_audio,
                    language=language
                )

                if asr_result and asr_result.text.strip():
                    transcripts.append(SpeakerTranscript(
                        speaker_id=segment.speaker_id,
                        start_ms=segment.start_ms,
                        end_ms=segment.end_ms,
                        text=asr_result.text,
                        confidence=asr_result.confidence
                    ))
            except Exception as e:
                logger.error(f"Failed to transcribe segment {segment.speaker_id}: {e}")
                # 继续处理其他片段

        return TranscriptWithSpeakers(
            transcripts=transcripts,
            num_speakers=diarization_result.num_speakers
        )

    async def get_speaker_statistics(
        self,
        diarization_result: DiarizationResult
    ) -> dict:
        """获取说话人统计信息

        Args:
            diarization_result: 说话人分离结果

        Returns:
            统计信息字典
        """
        speaker_stats = {}

        for segment in diarization_result.segments:
            speaker_id = segment.speaker_id

            if speaker_id not in speaker_stats:
                speaker_stats[speaker_id] = {
                    "total_duration_ms": 0,
                    "segment_count": 0,
                    "segments": []
                }

            speaker_stats[speaker_id]["total_duration_ms"] += segment.duration_ms
            speaker_stats[speaker_id]["segment_count"] += 1
            speaker_stats[speaker_id]["segments"].append({
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "duration_ms": segment.duration_ms
            })

        # 计算百分比
        total_duration = sum(s["total_duration_ms"] for s in speaker_stats.values())

        for speaker_id in speaker_stats:
            percentage = (speaker_stats[speaker_id]["total_duration_ms"] / total_duration * 100) if total_duration > 0 else 0
            speaker_stats[speaker_id]["percentage"] = round(percentage, 2)

        return speaker_stats
