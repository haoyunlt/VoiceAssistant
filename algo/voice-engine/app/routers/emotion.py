"""
情感识别API路由
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.emotion_recognition_service import get_emotion_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/emotion", tags=["emotion"])


class EmotionRecognitionRequest(BaseModel):
    """情感识别请求"""

    sample_rate: Optional[int] = 16000


class EmotionRecognitionResponse(BaseModel):
    """情感识别响应"""

    emotion: str
    confidence: float
    probabilities: dict
    features: dict
    error: Optional[str] = None


@router.post("/recognize", response_model=EmotionRecognitionResponse)
async def recognize_emotion(
    audio: UploadFile = File(..., description="音频文件（WAV/MP3/PCM）"),
    sample_rate: int = Form(16000, description="采样率"),
):
    """
    识别音频中的情感

    支持的情感类别：
    - neutral: 中性
    - happy: 快乐
    - sad: 悲伤
    - angry: 愤怒
    - fearful: 恐惧
    - disgusted: 厌恶
    - surprised: 惊讶

    特征提取：
    - MFCC（梅尔频率倒谱系数）
    - Chroma（色度特征）
    - Mel Spectrogram（梅尔频谱）
    - ZCR（零交叉率）
    - Spectral Centroid（谱质心）
    - Spectral Rolloff（谱滚降）
    - RMS Energy（能量）

    示例请求（curl）:
    ```bash
    curl -X POST "http://localhost:8004/api/v1/emotion/recognize" \\
      -F "audio=@audio.wav" \\
      -F "sample_rate=16000"
    ```

    示例响应:
    ```json
    {
      "emotion": "happy",
      "confidence": 0.75,
      "probabilities": {
        "neutral": 0.15,
        "happy": 0.75,
        "sad": 0.05,
        "angry": 0.03,
        "fearful": 0.01,
        "disgusted": 0.00,
        "surprised": 0.01
      },
      "features": {
        "feature_count": 194,
        "mean": 0.023,
        "std": 8.456,
        "min": -45.67,
        "max": 123.45
      }
    }
    ```
    """
    try:
        # 读取音频数据
        audio_data = await audio.read()

        if len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="音频文件为空")

        # 获取情感识别服务
        service = get_emotion_service()

        # 识别情感
        result = service.recognize(audio_data, sample_rate)

        return EmotionRecognitionResponse(**result)

    except Exception as e:
        logger.error(f"情感识别失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emotions")
async def list_emotions():
    """
    获取支持的情感列表

    返回系统支持的所有情感类别

    示例响应:
    ```json
    {
      "emotions": [
        "neutral",
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgusted",
        "surprised"
      ],
      "count": 7
    }
    ```
    """
    service = get_emotion_service()
    return {"emotions": service.EMOTIONS, "count": len(service.EMOTIONS)}


@router.get("/health")
async def emotion_service_health():
    """
    情感识别服务健康检查

    检查服务是否正常运行，模型是否加载

    示例响应:
    ```json
    {
      "status": "healthy",
      "model_loaded": true,
      "scaler_loaded": true
    }
    ```
    """
    service = get_emotion_service()
    return {
        "status": "healthy",
        "model_loaded": service.model is not None,
        "scaler_loaded": service.scaler is not None,
    }
