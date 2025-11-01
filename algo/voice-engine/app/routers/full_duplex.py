"""
全双工对话 WebSocket路由
支持实时打断处理和双向通信
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/full-duplex", tags=["Full Duplex"])

# 全局服务实例（延迟初始化）
interrupt_handler_service = None


async def get_interrupt_handler_service():
    """获取或初始化打断处理服务"""
    global interrupt_handler_service

    if interrupt_handler_service is None:
        logger.info("Initializing InterruptHandlerService...")
        from app.services.interrupt_handler_service import InterruptHandlerService
        from app.services.vad_service import VADService

        vad_service = VADService()

        interrupt_handler_service = InterruptHandlerService(
            vad_service=vad_service,
            interrupt_threshold=0.5,
            interrupt_duration=0.3,
        )
        logger.info("InterruptHandlerService initialized")

    return interrupt_handler_service


@router.websocket("/stream")
async def full_duplex_stream(websocket: WebSocket):
    """
    全双工语音对话流

    支持特性:
    - 实时语音识别（ASR）
    - 实时语音合成播放（TTS）
    - 打断检测与处理
    - 双向通信

    协议:

    **客户端 → 服务端**:
    ```json
    {
        "type": "audio",
        "data": "base64_encoded_audio"
    }
    {
        "type": "control",
        "action": "pause" | "resume" | "stop"
    }
    ```

    **服务端 → 客户端**:
    ```json
    {
        "type": "transcription",
        "text": "识别的文本"
    }
    {
        "type": "audio",
        "data": "base64_encoded_tts_audio"
    }
    {
        "type": "interrupt",
        "message": "检测到打断"
    }
    {
        "type": "playback_state",
        "state": "playing" | "paused" | "idle"
    }
    {
        "type": "heartbeat",
        "timestamp": 1234567890.123
    }
    ```

    工作流程:
    1. 客户端发送音频流
    2. 服务端实时ASR识别
    3. 服务端生成响应并开始TTS播放
    4. 同时监听用户语音，检测打断
    5. 检测到打断立即停止TTS
    6. 处理新的用户输入
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())
    logger.info(f"[FullDuplex {session_id}] Connection established")

    service = await get_interrupt_handler_service()

    # 创建会话
    session = service.create_session(session_id)

    # 启动心跳任务
    async def send_heartbeat():
        while True:
            try:
                await asyncio.sleep(1.0)
                await websocket.send_json(
                    {"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()}
                )
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())

    # 启动TTS播放任务
    async def play_tts_audio():
        while True:
            try:
                # 从队列获取音频
                tts_audio = await session["tts_audio_queue"].get()

                # 检查播放状态
                state = service.get_playback_state(session_id)

                if state == "interrupted" or state == "idle":
                    logger.info(f"[FullDuplex {session_id}] Playback interrupted, skipping")
                    continue

                # 发送音频到客户端
                import base64

                audio_base64 = base64.b64encode(tts_audio).decode("utf-8")

                await websocket.send_json({"type": "audio", "data": audio_base64, "format": "pcm"})

                # 发送播放状态
                await websocket.send_json(
                    {"type": "playback_state", "state": state.value if state else "idle"}
                )

            except Exception as e:
                logger.error(f"TTS playback error: {e}")
                break

    playback_task = asyncio.create_task(play_tts_audio())

    try:
        while True:
            # 接收客户端消息
            message = await websocket.receive_json()

            msg_type = message.get("type")

            if msg_type == "audio":
                # 音频数据（用于ASR和打断检测）
                import base64

                audio_data = base64.b64decode(message.get("data", ""))

                # 检测打断
                interrupt_detected = await service.detect_interrupt(
                    session_id=session_id, audio_chunk=audio_data, sample_rate=16000
                )

                if interrupt_detected:
                    # 处理打断
                    result = await service.handle_interrupt(session_id)

                    await websocket.send_json(
                        {
                            "type": "interrupt",
                            "message": "Interrupt detected, stopping playback",
                            "timestamp": result.get("timestamp"),
                        }
                    )

                    logger.info(f"[FullDuplex {session_id}] Interrupt handled")

                # TODO: 这里可以集成ASR服务识别音频
                # transcription = await asr_service.transcribe(audio_data)
                # await websocket.send_json({"type": "transcription", "text": transcription})

            elif msg_type == "control":
                # 控制命令
                action = message.get("action")

                if action == "pause":
                    await service.pause_playback(session_id)
                    await websocket.send_json({"type": "playback_state", "state": "paused"})

                elif action == "resume":
                    await service.resume_playback(session_id)
                    await websocket.send_json({"type": "playback_state", "state": "playing"})

                elif action == "stop":
                    await service.stop_playback(session_id)
                    await websocket.send_json({"type": "playback_state", "state": "idle"})

            elif msg_type == "tts_request":
                # TTS请求（客户端请求合成语音）
                text = message.get("text", "")

                # TODO: 集成TTS服务
                # tts_audio = await tts_service.synthesize(text)
                # await service.start_playback(session_id, tts_audio)

                logger.info(f"[FullDuplex {session_id}] TTS request: {text}")

    except WebSocketDisconnect:
        logger.info(f"[FullDuplex {session_id}] Client disconnected")

    except Exception as e:
        logger.error(f"[FullDuplex {session_id}] Error: {e}", exc_info=True)

    finally:
        # 清理
        heartbeat_task.cancel()
        playback_task.cancel()
        await service.cleanup_session(session_id)
        logger.info(f"[FullDuplex {session_id}] Session cleaned up")


@router.get("/stats")
async def get_statistics():
    """
    获取全双工服务统计信息

    返回:
    - total_sessions: 总会话数
    - active_sessions: 活跃会话数
    - interrupted_sessions: 被打断的会话数
    """
    service = await get_interrupt_handler_service()

    if service is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Service not available")

    return service.get_statistics()
