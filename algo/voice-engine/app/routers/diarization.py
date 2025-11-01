"""
说话人分离API路由
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.diarization_service import get_diarization_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diarization", tags=["diarization"])


class DiarizationSegment(BaseModel):
    """分离片段"""

    start: float
    end: float
    duration: float
    speaker: str


class DiarizationResponse(BaseModel):
    """说话人分离响应"""

    segments: list[DiarizationSegment]
    speakers: list[str]
    total_speakers: int
    duration: float
    mock: bool | None = None
    error: str | None = None


class SpeakerStatistics(BaseModel):
    """说话人统计"""

    total_duration: float
    total_speakers: int
    speakers: dict


@router.post("/analyze", response_model=DiarizationResponse)
async def analyze_speakers(
    audio: UploadFile = File(..., description="音频文件（WAV/MP3）"),
    sample_rate: int = Form(16000, description="采样率"),
    min_speakers: int | None = Form(None, description="最小说话人数"),
    max_speakers: int | None = Form(None, description="最大说话人数"),
):
    """
    执行说话人分离分析

    识别音频中的不同说话人，并标记每个说话人的发言时间段

    特性：
    - 自动检测说话人数量
    - 精确的时间标注
    - 支持多人对话场景
    - 基于Pyannote-audio深度学习模型

    示例请求（curl）:
    ```bash
    curl -X POST "http://localhost:8004/api/v1/diarization/analyze" \\
      -F "audio=@meeting.wav" \\
      -F "sample_rate=16000" \\
      -F "min_speakers=2" \\
      -F "max_speakers=4"
    ```

    示例响应:
    ```json
    {
      "segments": [
        {
          "start": 0.0,
          "end": 3.5,
          "duration": 3.5,
          "speaker": "SPEAKER_00"
        },
        {
          "start": 3.8,
          "end": 7.2,
          "duration": 3.4,
          "speaker": "SPEAKER_01"
        },
        {
          "start": 7.5,
          "end": 12.0,
          "duration": 4.5,
          "speaker": "SPEAKER_00"
        }
      ],
      "speakers": ["SPEAKER_00", "SPEAKER_01"],
      "total_speakers": 2,
      "duration": 12.0
    }
    ```

    注意：
    - 需要设置HF_TOKEN环境变量（HuggingFace token）
    - 如果未设置token，将使用简单的Mock分离
    """
    try:
        # 读取音频数据
        audio_data = await audio.read()

        if len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="音频文件为空")

        # 获取说话人分离服务
        service = get_diarization_service()

        # 执行分离
        result = service.diarize(
            audio_data=audio_data,
            sample_rate=sample_rate,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        return DiarizationResponse(**result)

    except Exception as e:
        logger.error(f"说话人分离失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/statistics")
async def get_speaker_statistics(
    audio: UploadFile = File(..., description="音频文件"),
    sample_rate: int = Form(16000, description="采样率"),
):
    """
    获取说话人统计信息

    分析每个说话人的发言时长、占比等统计数据

    示例响应:
    ```json
    {
      "total_duration": 120.5,
      "total_speakers": 3,
      "speakers": {
        "SPEAKER_00": {
          "speaking_time": 45.2,
          "percentage": 37.5,
          "segment_count": 12
        },
        "SPEAKER_01": {
          "speaking_time": 52.8,
          "percentage": 43.8,
          "segment_count": 15
        },
        "SPEAKER_02": {
          "speaking_time": 22.5,
          "percentage": 18.7,
          "segment_count": 8
        }
      }
    }
    ```
    """
    try:
        # 读取音频数据
        audio_data = await audio.read()

        if len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="音频文件为空")

        # 获取说话人分离服务
        service = get_diarization_service()

        # 执行分离
        diarization_result = service.diarize(
            audio_data=audio_data,
            sample_rate=sample_rate,
        )

        # 计算统计信息
        statistics = service.get_speaker_statistics(diarization_result)

        return SpeakerStatistics(**statistics)

    except Exception as e:
        logger.error(f"获取说话人统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def diarization_service_health():
    """
    说话人分离服务健康检查

    检查Pyannote模型是否加载成功

    示例响应:
    ```json
    {
      "status": "healthy",
      "pipeline_loaded": true,
      "device": "cpu",
      "model": "pyannote/speaker-diarization-3.1"
    }
    ```
    """
    service = get_diarization_service()
    return {
        "status": "healthy",
        "pipeline_loaded": service.pipeline is not None,
        "device": service.device,
        "model": "pyannote/speaker-diarization-3.1" if service.pipeline else "mock",
    }
