"""
Full Duplex Engine - 完整实现
全双工语音交互引擎，支持同时录音和播放，实现打断功能
"""

import asyncio
import base64
import builtins
import contextlib
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class FullDuplexEngine:
    """
    全双工语音交互引擎
    支持同时录音和播放，实现打断功能
    """

    def __init__(self, asr_service, tts_service, vad_service):
        self.asr_service = asr_service
        self.tts_service = tts_service
        self.vad_service = vad_service

        self.is_playing = False
        self.playback_task = None
        self.asr_task = None
        self.vad_task = None

        # 音频缓冲
        self.audio_buffer = bytearray()
        self.min_chunk_size = 16000 * 2  # 2秒

    async def start_session(self, websocket: WebSocket, config: dict = None):
        """
        启动全双工会话

        Args:
            websocket: WebSocket 连接
            config: 配置参数
        """
        logger.info("Starting full duplex session")

        # 配置
        self.config = config or {}
        self.language = self.config.get("language", "zh")
        self.voice = self.config.get("voice", "zh-CN-XiaoxiaoNeural")
        self.enable_vad = self.config.get("enable_vad", True)

        # 创建任务
        try:
            # 并发运行 ASR 和 TTS 循环
            self.asr_task = asyncio.create_task(self._asr_loop(websocket))
            tts_task = asyncio.create_task(self._tts_loop(websocket))

            # VAD 监控（用于打断检测）
            if self.enable_vad:
                self.vad_task = asyncio.create_task(self._vad_loop(websocket))
                await asyncio.gather(self.asr_task, tts_task, self.vad_task)
            else:
                await asyncio.gather(self.asr_task, tts_task)

        except Exception as e:
            logger.error(f"Full duplex session error: {e}", exc_info=True)
        finally:
            await self._cleanup()
            logger.info("Full duplex session ended")

    async def _asr_loop(self, websocket: WebSocket):
        """ASR 循环 - 持续接收和识别音频"""
        logger.info("ASR loop started")

        try:
            while True:
                # 接收消息
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                try:
                    data = json.loads(message.get("text", "{}"))
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "audio":
                    # 处理音频数据
                    audio_b64 = data.get("audio", "")
                    audio_chunk = base64.b64decode(audio_b64)
                    self.audio_buffer.extend(audio_chunk)

                    # 检查是否有足够数据
                    if len(self.audio_buffer) >= self.min_chunk_size:
                        await self._process_audio_chunk(websocket)

                elif msg_type == "tts_request":
                    # TTS 请求
                    text = data.get("text", "")
                    if text:
                        await self._handle_tts_request(websocket, text)

                elif msg_type == "end":
                    break

        except asyncio.CancelledError:
            logger.info("ASR loop cancelled")
        except Exception as e:
            logger.error(f"ASR loop error: {e}")

    async def _process_audio_chunk(self, websocket: WebSocket):
        """处理音频块"""
        try:
            # VAD 检测
            audio_bytes = bytes(self.audio_buffer)
            has_speech = await self.vad_service.detect(audio_bytes)

            if has_speech:
                # 如果正在播放，停止播放（打断）
                if self.is_playing:
                    await self._stop_playback(websocket)

                # ASR 识别
                result = await self.asr_service.recognize(
                    audio_data=audio_bytes, language=self.language
                )

                # 发送识别结果
                if result.get("text"):
                    await websocket.send_json(
                        {
                            "type": "asr_result",
                            "text": result["text"],
                            "confidence": result.get("confidence", 0.0),
                            "is_final": True,
                        }
                    )

            # 清空缓冲区
            self.audio_buffer = bytearray()

        except Exception as e:
            logger.error(f"Audio processing error: {e}")

    async def _tts_loop(self, _websocket: WebSocket):
        """TTS 循环 - 等待 TTS 请求并播放"""
        logger.info("TTS loop started")

        try:
            # TTS 请求通过消息队列处理，这里只是占位
            # 实际的 TTS 处理在 _handle_tts_request 中
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("TTS loop cancelled")

    async def _handle_tts_request(self, websocket: WebSocket, text: str):
        """
        处理 TTS 请求

        Args:
            websocket: WebSocket 连接
            text: 要合成的文本
        """
        try:
            # 合成语音
            audio_data = await self.tts_service.synthesize(
                text=text, voice=self.voice, language=self.language
            )

            # 流式播放
            self.playback_task = asyncio.create_task(self._stream_audio(websocket, audio_data))

        except Exception as e:
            logger.error(f"TTS request failed: {e}")
            await websocket.send_json({"type": "error", "message": f"TTS 失败: {str(e)}"})

    async def _stream_audio(self, websocket: WebSocket, audio: bytes):
        """
        流式播放音频

        Args:
            websocket: WebSocket 连接
            audio: 音频数据
        """
        self.is_playing = True

        try:
            # 分块发送
            chunk_size = 4096
            total_chunks = (len(audio) + chunk_size - 1) // chunk_size

            for i in range(0, len(audio), chunk_size):
                # 检查是否被取消
                if asyncio.current_task().cancelled():
                    break

                chunk = audio[i : i + chunk_size]
                chunk_num = i // chunk_size + 1

                await websocket.send_json(
                    {
                        "type": "audio_chunk",
                        "audio": base64.b64encode(chunk).decode(),
                        "chunk_num": chunk_num,
                        "total_chunks": total_chunks,
                        "is_last": i + chunk_size >= len(audio),
                    }
                )

                # 小延迟，避免过快
                await asyncio.sleep(0.01)

            logger.info("Audio playback completed")

        except asyncio.CancelledError:
            logger.info("Audio playback cancelled (interrupted)")
        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
        finally:
            self.is_playing = False

    async def _stop_playback(self, websocket: WebSocket):
        """
        停止音频播放

        Args:
            websocket: WebSocket 连接
        """
        logger.info("Stopping playback...")

        self.is_playing = False

        # 取消播放任务
        if self.playback_task and not self.playback_task.done():
            self.playback_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.playback_task

        # 发送停止通知
        with contextlib.suppress(builtins.BaseException):
            await websocket.send_json({"type": "playback_stopped", "reason": "interrupted_by_user"})

        logger.info("Playback stopped")

    async def _vad_loop(self, _websocket: WebSocket):
        """VAD 监控循环 - 用于打断检测"""
        logger.info("VAD loop started")

        try:
            # VAD 监控逻辑
            # 在实际使用中，VAD 已经在 _process_audio_chunk 中处理
            # 这里只是一个占位循环
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("VAD loop cancelled")

    async def _cleanup(self):
        """清理资源"""
        logger.info("Cleaning up full duplex session...")

        self.is_playing = False

        # 取消所有任务
        tasks = [self.asr_task, self.playback_task, self.vad_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        # 等待任务完成
        for task in tasks:
            if task:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        # 清空缓冲
        self.audio_buffer = bytearray()

        logger.info("Cleanup completed")
