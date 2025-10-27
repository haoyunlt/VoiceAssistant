"""
Streaming ASR WebSocket Router
流式语音识别 WebSocket 接口
"""

import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.services.streaming_asr_service import StreamingASRService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/api/v1/asr/recognize/stream")
async def recognize_stream(websocket: WebSocket):
    """
    WebSocket 流式语音识别

    客户端发送格式:
    {
        "type": "audio",
        "audio": "base64_encoded_audio_data",
        "sample_rate": 16000,
        "format": "pcm"
    }

    或结束信号:
    {
        "type": "end"
    }

    服务端返回:
    {
        "type": "partial",  // 或 "final"
        "text": "识别文本",
        "confidence": 0.95,
        "is_final": false
    }
    """
    await websocket.accept()

    # 获取应用状态中的模型
    app = websocket.app
    whisper_model = getattr(app.state, 'whisper_model', None)
    vad_model = getattr(app.state, 'vad_model', None)

    if not whisper_model or not vad_model:
        await websocket.send_json({
            "type": "error",
            "message": "ASR 或 VAD 模型未加载"
        })
        await websocket.close()
        return

    # 初始化流式识别器
    streaming_asr = StreamingASRService(
        whisper_model=whisper_model,
        vad_model=vad_model
    )

    # 音频缓冲区和结果缓存
    audio_buffer = bytearray()
    partial_results = []

    try:
        logger.info("WebSocket streaming ASR session started")

        while True:
            # 接收音频数据
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                logger.info("Client disconnected")
                break

            # 解析消息
            try:
                data = json.loads(message.get("text", "{}"))
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的 JSON 格式"
                })
                continue

            message_type = data.get("type")

            if message_type == "audio":
                # 处理音频数据
                try:
                    # 解码 base64 音频
                    audio_b64 = data.get("audio", "")
                    audio_chunk = base64.b64decode(audio_b64)
                    audio_buffer.extend(audio_chunk)

                    # 检查是否有足够数据进行识别
                    if len(audio_buffer) >= streaming_asr.min_chunk_size:
                        # 执行 VAD
                        speech_segments = streaming_asr.detect_speech(bytes(audio_buffer))

                        # 对语音段进行识别
                        for segment in speech_segments:
                            result = await streaming_asr.recognize_segment(segment)

                            if result.get("text"):
                                # 发送部分结果
                                await websocket.send_json({
                                    "type": "partial",
                                    "text": result["text"],
                                    "confidence": result["confidence"],
                                    "is_final": False,
                                    "start_time": result.get("start_time", 0),
                                    "end_time": result.get("end_time", 0)
                                })

                                # 缓存部分结果
                                partial_results.append(result)

                        # 清空已处理的部分
                        audio_buffer = bytearray()

                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"音频处理失败: {str(e)}"
                    })

            elif message_type == "end":
                # 处理剩余缓冲区
                if len(audio_buffer) > 0:
                    try:
                        speech_segments = streaming_asr.detect_speech(bytes(audio_buffer))

                        for segment in speech_segments:
                            result = await streaming_asr.recognize_segment(segment)
                            if result.get("text"):
                                partial_results.append(result)
                    except Exception as e:
                        logger.error(f"Final buffer processing error: {e}")

                # 合并所有部分结果
                final_text = streaming_asr.merge_partial_results(partial_results)

                # 发送最终结果
                await websocket.send_json({
                    "type": "final",
                    "text": final_text,
                    "confidence": sum(r["confidence"] for r in partial_results) / len(partial_results) if partial_results else 0.0,
                    "is_final": True,
                    "segments_count": len(partial_results)
                })

                logger.info(f"Session ended. Final text: {final_text}")
                break

            elif message_type == "ping":
                # 心跳
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {message_type}"
                })

    except WebSocketDisconnect:
        logger.info("Client disconnected (WebSocketDisconnect)")

    except Exception as e:
        logger.error(f"Streaming ASR error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            })
        except:
            pass

    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info("WebSocket streaming ASR session closed")


@router.get("/api/v1/asr/stream/info")
async def stream_info():
    """
    获取流式识别配置信息
    """
    return JSONResponse({
        "sample_rate": 16000,
        "format": "pcm_s16le",
        "channels": 1,
        "min_chunk_duration_ms": 2000,
        "vad_enabled": True,
        "supported_languages": ["zh", "en", "auto"]
    })
