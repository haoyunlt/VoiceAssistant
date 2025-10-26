"""
TTS (Text-to-Speech) endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.logging_config import get_logger
from app.models.voice import TTSRequest, TTSResponse
from app.services.tts_service import TTSService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])

# 全局服务实例
tts_service = TTSService()


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(request: TTSRequest):
    """
    文本转语音（批量模式）

    - **text**: 待合成文本
    - **voice**: 音色（可选）
    - **rate**: 语速（可选，如 +10%）
    - **pitch**: 音调（可选，如 +5Hz）
    - **format**: 音频格式（mp3, wav, opus）
    - **cache_key**: 缓存键（可选）
    """
    try:
        logger.info(f"TTS request: text length={len(request.text)}, voice={request.voice}")
        response = await tts_service.synthesize(request)
        logger.info(f"TTS completed: duration={response.duration_ms}ms, cached={response.cached}")
        return response
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")


@router.post("/synthesize/stream")
async def synthesize_stream(request: TTSRequest):
    """
    流式文本转语音

    - **text**: 待合成文本
    - **voice**: 音色（可选）
    - **rate**: 语速（可选）
    - **pitch**: 音调（可选）

    返回音频流
    """
    try:
        logger.info(f"TTS stream request: text length={len(request.text)}")

        # 生成音频流
        audio_stream = await tts_service.synthesize_stream(request)

        return StreamingResponse(
            audio_stream,
            media_type=f"audio/{request.format}",
            headers={
                "Content-Disposition": f'attachment; filename="speech.{request.format}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    except Exception as e:
        logger.error(f"TTS stream synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS stream synthesis failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """
    列出可用的音色

    返回支持的音色列表
    """
    try:
        voices = await tts_service.list_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Failed to list voices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")
