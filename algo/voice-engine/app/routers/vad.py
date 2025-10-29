"""
VAD (Voice Activity Detection) endpoints
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.voice import VADRequest, VADResponse
from app.services.vad_service import VADService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/vad", tags=["VAD"])

# 全局服务实例
vad_service = VADService()


@router.post("/detect", response_model=VADResponse)
async def detect_voice_activity(request: VADRequest):
    """
    语音活动检测

    - **audio_url**: 音频文件 URL
    - **audio_base64**: 音频文件 Base64 编码
    - **threshold**: 阈值 (0-1)
    """
    try:
        logger.info(f"VAD request: threshold={request.threshold}")
        response = await vad_service.detect(request)
        logger.info(
            f"VAD completed: segments={len(response.segments)}, speech_ratio={response.speech_ratio:.2%}"
        )
        return response
    except Exception as e:
        logger.error(f"VAD detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"VAD detection failed: {str(e)}")


@router.post("/detect/upload", response_model=VADResponse)
async def detect_upload(file: UploadFile = File(...), threshold: float = None):
    """
    语音活动检测（文件上传）

    - **file**: 音频文件
    - **threshold**: 阈值 (0-1)
    """
    try:
        logger.info(f"VAD upload request: filename={file.filename}")

        # 读取文件内容
        audio_data = await file.read()

        # 检测
        response = await vad_service.detect_from_bytes(audio_data=audio_data, threshold=threshold)

        logger.info(f"VAD completed: segments={len(response.segments)}")
        return response

    except Exception as e:
        logger.error(f"VAD detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"VAD detection failed: {str(e)}")
