"""
ASR (Automatic Speech Recognition) endpoints
"""

import builtins
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.voice import ASRRequest, ASRResponse, StreamASRRequest
from app.services.asr_service import ASRService
from app.services.multi_vendor_adapter import get_multi_vendor_adapter
from app.services.streaming_asr_service import StreamingASRService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/asr", tags=["ASR"])

# 全局服务实例
asr_service = ASRService()
streaming_asr_service = None  # 将在 startup 时初始化


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


@router.websocket("/ws/stream")
async def websocket_asr_stream(websocket: WebSocket):
    """
    WebSocket 流式 ASR 识别

    流程:
    1. 客户端连接并发送配置 JSON: {"model_size": "base", "language": "zh", "vad_enabled": true}
    2. 客户端发送音频数据流 (二进制)
    3. 服务端返回识别结果流 (JSON)
       - {"type": "session_start", ...}
       - {"type": "speech_start", ...}
       - {"type": "partial_result", "text": "...", "is_final": false}
       - {"type": "final_result", "text": "...", "is_final": true}
       - {"type": "speech_end", ...}
       - {"type": "session_end", ...}
    4. 客户端发送结束信号: {"type": "end_stream"}
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        # 1. 接收配置
        config_msg = await websocket.receive_json()
        model_size = config_msg.get("model_size", "base")
        language = config_msg.get("language", "zh")
        vad_enabled = config_msg.get("vad_enabled", True)

        logger.info(f"Streaming ASR config: model_size={model_size}, language={language}, vad_enabled={vad_enabled}")

        # 2. 初始化流式 ASR 服务 (每个连接独立实例)
        service = StreamingASRService(
            model_size=model_size,
            language=language,
            vad_enabled=vad_enabled,
            chunk_duration_ms=300,
            vad_mode=3
        )

        # 3. 音频生成器
        async def audio_generator() -> AsyncIterator[bytes]:
            """从 WebSocket 接收音频数据"""
            while True:
                try:
                    message = await websocket.receive()

                    if "bytes" in message:
                        # 接收到音频数据
                        yield message["bytes"]

                    elif "text" in message:
                        # 接收到控制命令
                        cmd = json.loads(message["text"])
                        if cmd.get("type") == "end_stream":
                            logger.info("Received end_stream command")
                            break

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected during audio reception")
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio data: {e}")
                    break

        # 4. 处理流式识别并返回结果
        async for result in service.process_stream(audio_generator()):
            try:
                await websocket.send_json(result)
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during result sending")
                break

        logger.info("Streaming ASR session completed")

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config: {e}")
        await websocket.send_json({
            "type": "error",
            "error": f"Invalid configuration JSON: {str(e)}"
        })

    except Exception as e:
        logger.error(f"Streaming ASR error: {e}", exc_info=True)
        with contextlib.suppress(builtins.BaseException):
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })

    finally:
        try:
            await websocket.close()
            logger.info("WebSocket connection closed")
        except:
            pass


# ===== Multi-Vendor Endpoints =====


class MultiVendorASRRequest(BaseModel):
    """多厂商 ASR 请求"""
    audio_base64: str
    language: str = "zh"
    model_size: str = "base"
    vendor_preference: Literal["azure", "faster-whisper"] | None = None


@router.post("/recognize/multi-vendor", summary="多厂商 ASR 识别（自动降级）")
async def recognize_multi_vendor(request: MultiVendorASRRequest):
    """
    多厂商 ASR 识别（支持自动降级）

    降级策略：
    1. 如果 vendor_preference 为 "azure" 且 Azure 可用 -> Azure
    2. 否则 -> Faster-Whisper

    Args:
        - **audio_base64**: 音频文件 Base64 编码
        - **language**: 语言代码（zh, en, ja, etc.）
        - **model_size**: Faster-Whisper 模型大小（如果降级到 Faster-Whisper）
        - **vendor_preference**: 首选厂商（azure | faster-whisper | None）

    Returns:
        识别结果字典:
        {
            "text": str,
            "confidence": float,
            "language": str,
            "vendor": str,  # "azure" | "faster-whisper"
            "error": str (optional)
        }
    """
    try:
        import base64

        # 解码音频
        audio_data = base64.b64decode(request.audio_base64)

        # 获取适配器
        adapter = get_multi_vendor_adapter()

        # 如果指定了厂商偏好，临时修改适配器配置
        if request.vendor_preference:
            original_preference = adapter.preferred_asr
            adapter.preferred_asr = request.vendor_preference

            result = await adapter.recognize(
                audio_data=audio_data,
                language=request.language,
                model_size=request.model_size
            )

            # 恢复原始配置
            adapter.preferred_asr = original_preference
        else:
            result = await adapter.recognize(
                audio_data=audio_data,
                language=request.language,
                model_size=request.model_size
            )

        logger.info(f"Multi-vendor ASR completed: vendor={result.get('vendor')}, text_length={len(result.get('text', ''))}")
        return result

    except Exception as e:
        logger.error(f"Multi-vendor ASR failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-vendor ASR failed: {str(e)}")


@router.get("/vendors/status", summary="获取所有 ASR 厂商状态")
async def get_vendors_status():
    """
    获取所有 ASR 厂商的状态

    Returns:
        状态字典
    """
    try:
        adapter = get_multi_vendor_adapter()
        status = adapter.get_status()

        # 仅返回 ASR 相关状态
        return {
            "preferred_asr": status["preferred_asr"],
            "services": {
                "azure": status["services"].get("azure", {}),
                "faster_whisper": status["services"].get("faster_whisper", {}),
            }
        }

    except Exception as e:
        logger.error(f"Failed to get vendors status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
