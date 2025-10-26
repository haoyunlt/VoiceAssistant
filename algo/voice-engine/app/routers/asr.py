"""
ASR (Automatic Speech Recognition) endpoints
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.logging_config import get_logger
from app.models.voice import ASRRequest, ASRResponse, StreamASRRequest
from app.services.asr_service import ASRService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/asr", tags=["ASR"])

# 全局服务实例
asr_service = ASRService()


@router.post("/recognize", response_model=ASRResponse)
async def recognize_speech(request: ASRRequest):
    """
    语音识别（批量模式）

    - **audio_url**: 音频文件 URL
    - **audio_base64**: 音频文件 Base64 编码
    - **language**: 语言代码（可选）
    - **enable_vad**: 是否启用 VAD
    - **task**: transcribe（转录）或 translate（翻译）
    """
    try:
        logger.info(f"ASR recognize request: language={request.language}, enable_vad={request.enable_vad}")
        response = await asr_service.recognize(request)
        logger.info(f"ASR completed: text length={len(response.text)}, language={response.language}")
        return response
    except Exception as e:
        logger.error(f"ASR recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ASR recognition failed: {str(e)}")


@router.post("/recognize/upload", response_model=ASRResponse)
async def recognize_upload(
    file: UploadFile = File(...),
    language: str = None,
    enable_vad: bool = True,
    task: str = "transcribe",
):
    """
    语音识别（文件上传）

    - **file**: 音频文件
    - **language**: 语言代码（可选）
    - **enable_vad**: 是否启用 VAD
    - **task**: transcribe（转录）或 translate（翻译）
    """
    try:
        logger.info(f"ASR upload request: filename={file.filename}")

        # 读取文件内容
        audio_data = await file.read()

        # 识别
        response = await asr_service.recognize_from_bytes(
            audio_data=audio_data,
            language=language,
            enable_vad=enable_vad,
            task=task,
        )

        logger.info(f"ASR completed: text length={len(response.text)}")
        return response

    except Exception as e:
        logger.error(f"ASR recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ASR recognition failed: {str(e)}")


@router.post("/stream")
async def stream_recognize(request: StreamASRRequest):
    """
    流式语音识别（WebSocket 或 SSE）

    - **session_id**: 会话 ID
    - **language**: 语言代码（可选）
    - **enable_vad**: 是否启用 VAD

    返回 Server-Sent Events 流
    """
    try:
        logger.info(f"Stream ASR request: session_id={request.session_id}")

        # TODO: 实现流式识别
        # 这里返回一个简化的实现，实际应使用 WebSocket 或 SSE

        async def generate():
            yield f"data: {{\"session_id\": \"{request.session_id}\", \"status\": \"started\"}}\n\n"
            # 实际流式识别逻辑
            yield f"data: {{\"session_id\": \"{request.session_id}\", \"status\": \"completed\"}}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Stream ASR failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stream ASR failed: {str(e)}")
