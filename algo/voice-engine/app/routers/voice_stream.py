"""
实时语音流 WebSocket API
"""

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice-stream"])

# 全局服务实例（延迟初始化）
realtime_service = None


async def get_realtime_service():
    """获取或初始化实时语音服务"""
    global realtime_service

    if realtime_service is None:
        logger.info("Initializing RealtimeVoiceService...")
        from app.services.asr_service import ASRService
        from app.services.realtime_voice_service import RealtimeVoiceService
        from app.services.vad_service import VADService

        # 初始化依赖服务
        asr_service = ASRService()
        vad_service = VADService()

        # 初始化实时语音服务
        realtime_service = RealtimeVoiceService(
            asr_service=asr_service,
            vad_service=vad_service,
            sample_rate=16000,
            vad_threshold=0.3,
            min_speech_duration=0.5,
            silence_duration=0.8,
            heartbeat_interval=1.0,
            session_timeout=300.0,
        )

        logger.info("RealtimeVoiceService initialized")

    return realtime_service


@router.websocket("/stream")
async def websocket_voice_stream(websocket: WebSocket):
    """
    WebSocket实时语音流

    流程:
    1. 客户端发送音频帧（binary，PCM 16bit 16kHz）
    2. 服务端VAD检测语音活动
    3. 检测到静音→触发ASR识别
    4. 返回识别结果（JSON）
    5. 定期发送心跳

    客户端发送:
    - Binary: PCM 16bit 16kHz mono 音频数据

    服务端返回:
    - {"type": "transcription", "text": "...", "confidence": 0.95, ...}
    - {"type": "heartbeat", "buffer_duration": 1.2, ...}
    - {"type": "error", "message": "..."}
    - {"type": "timeout", "message": "..."}

    示例客户端代码（JavaScript）:
    ```javascript
    const ws = new WebSocket('ws://localhost:8004/api/v1/voice/stream');

    ws.onopen = () => {
        console.log('Connected');
        // 开始录音并发送音频
        startRecording((audioData) => {
            ws.send(audioData);
        });
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'transcription') {
            console.log('识别结果:', data.text);
        } else if (data.type === 'heartbeat') {
            console.log('心跳:', data);
        }
    };
    ```
    """
    await websocket.accept()

    # 生成会话ID
    session_id = str(uuid.uuid4())
    logger.info(f"[Session {session_id}] WebSocket连接建立")

    # 获取服务实例
    service = await get_realtime_service()

    try:
        await service.handle_stream(websocket, session_id)

    except WebSocketDisconnect:
        logger.info(f"[Session {session_id}] 客户端断开连接")

    except Exception as e:
        logger.error(f"[Session {session_id}] 异常: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass

    finally:
        await service.cleanup_session(session_id)
        logger.info(f"[Session {session_id}] 会话清理完成")


@router.get("/stream/info")
async def stream_info():
    """
    获取流式语音配置信息

    Returns:
        配置信息
    """
    return JSONResponse(
        {
            "endpoint": "/api/v1/voice/stream",
            "protocol": "websocket",
            "audio_format": {
                "sample_rate": 16000,
                "format": "pcm_s16le",
                "channels": 1,
                "bit_depth": 16,
            },
            "features": {
                "vad_enabled": True,
                "real_time": True,
                "heartbeat": True,
                "auto_punctuation": False,
            },
            "limits": {
                "min_speech_duration_seconds": 0.5,
                "silence_trigger_seconds": 0.8,
                "session_timeout_seconds": 300,
                "heartbeat_interval_seconds": 1.0,
            },
            "supported_languages": ["zh", "en", "auto"],
        }
    )


@router.get("/stream/stats")
async def stream_stats():
    """
    获取流式语音统计信息

    Returns:
        统计信息
    """
    service = await get_realtime_service()

    return JSONResponse(
        {
            "active_sessions": service.get_session_count(),
            "service_status": "running",
        }
    )
