"""
实时语音流服务
WebSocket双向通信 + 实时VAD触发ASR
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Optional

import numpy as np
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RealtimeVoiceService:
    """实时语音流服务"""

    def __init__(
        self,
        asr_service,
        vad_service,
        sample_rate: int = 16000,
        vad_threshold: float = 0.3,
        min_speech_duration: float = 0.5,
        silence_duration: float = 0.8,
        heartbeat_interval: float = 1.0,
        session_timeout: float = 300.0,
    ):
        """
        初始化实时语音服务

        Args:
            asr_service: ASR服务
            vad_service: VAD服务
            sample_rate: 采样率（Hz）
            vad_threshold: VAD阈值
            min_speech_duration: 最小语音时长（秒）
            silence_duration: 静音触发时长（秒）
            heartbeat_interval: 心跳间隔（秒）
            session_timeout: 会话超时（秒）
        """
        self.asr = asr_service
        self.vad = vad_service
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.min_speech_duration = min_speech_duration
        self.silence_duration = silence_duration
        self.heartbeat_interval = heartbeat_interval
        self.session_timeout = session_timeout

        # 会话管理
        self.sessions: Dict[str, Dict] = {}

        logger.info(
            f"RealtimeVoiceService initialized: "
            f"sample_rate={sample_rate}, "
            f"vad_threshold={vad_threshold}, "
            f"min_speech_duration={min_speech_duration}"
        )

    async def handle_stream(self, websocket: WebSocket, session_id: str):
        """
        处理WebSocket音频流

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
        """
        # 初始化会话
        session = {
            "audio_buffer": bytearray(),
            "buffer_duration": 0.0,
            "is_speaking": False,
            "last_speech_time": 0.0,
            "last_activity_time": time.time(),
            "total_frames": 0,
            "recognition_count": 0,
        }
        self.sessions[session_id] = session

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(
            self._send_heartbeats(websocket, session_id)
        )

        # 启动超时检测任务
        timeout_task = asyncio.create_task(
            self._check_timeout(websocket, session_id)
        )

        try:
            logger.info(f"[Session {session_id}] Stream handling started")

            while True:
                # 接收音频数据（binary）
                data = await websocket.receive_bytes()

                # 更新活动时间
                session["last_activity_time"] = time.time()
                session["audio_buffer"].extend(data)
                session["buffer_duration"] += len(data) / (self.sample_rate * 2)
                session["total_frames"] += 1

                # 转换音频数据为float32
                audio_array = np.frombuffer(
                    bytes(session["audio_buffer"]), dtype=np.int16
                ).astype(np.float32) / 32768.0

                # VAD检测
                try:
                    speech_prob = await self._detect_speech(audio_array)
                except Exception as e:
                    logger.error(f"VAD detection failed: {e}")
                    speech_prob = 0.0

                # 状态转换
                if speech_prob > self.vad_threshold:
                    # 检测到语音
                    if not session["is_speaking"]:
                        logger.debug(
                            f"[Session {session_id}] Speech started "
                            f"(prob={speech_prob:.2f})"
                        )
                    session["is_speaking"] = True
                    session["last_speech_time"] = time.time()

                elif session["is_speaking"]:
                    # 当前在说话，检测静音
                    silence_duration = time.time() - session["last_speech_time"]

                    # 检测到语音结束
                    if (
                        silence_duration > self.silence_duration
                        and session["buffer_duration"] > self.min_speech_duration
                    ):
                        logger.info(
                            f"[Session {session_id}] Speech ended, "
                            f"duration={session['buffer_duration']:.2f}s, "
                            f"silence={silence_duration:.2f}s"
                        )

                        # 触发ASR
                        await self._trigger_asr(
                            websocket, session_id, bytes(session["audio_buffer"])
                        )

                        # 清空缓冲区
                        session["audio_buffer"].clear()
                        session["buffer_duration"] = 0.0
                        session["is_speaking"] = False
                        session["recognition_count"] += 1

        except asyncio.CancelledError:
            logger.info(f"[Session {session_id}] Stream handling cancelled")
            raise

        except Exception as e:
            logger.error(f"[Session {session_id}] Stream error: {e}", exc_info=True)
            try:
                await websocket.send_json(
                    {"type": "error", "message": f"Stream error: {str(e)}"}
                )
            except:
                pass

        finally:
            # 取消后台任务
            heartbeat_task.cancel()
            timeout_task.cancel()

            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            try:
                await timeout_task
            except asyncio.CancelledError:
                pass

    async def _detect_speech(self, audio_array: np.ndarray) -> float:
        """
        VAD语音检测

        Args:
            audio_array: 音频数组

        Returns:
            语音概率 (0-1)
        """
        # 调用VAD服务
        result = await self.vad.detect(
            audio_bytes=audio_array.tobytes(), sample_rate=self.sample_rate
        )

        # 返回平均语音概率
        if result and "speech_probs" in result:
            speech_probs = result["speech_probs"]
            if speech_probs:
                return float(np.mean(speech_probs))

        return 0.0

    async def _trigger_asr(
        self, websocket: WebSocket, session_id: str, audio_bytes: bytes
    ):
        """
        触发ASR识别

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
            audio_bytes: 音频字节数据
        """
        try:
            start_time = time.time()

            # 调用ASR服务
            result = await self.asr.transcribe(
                audio_bytes=audio_bytes, language="zh", sample_rate=self.sample_rate
            )

            asr_time = time.time() - start_time

            # 提取文本
            text = result.get("text", "").strip()

            if text:
                # 发送识别结果
                session = self.sessions.get(session_id)
                await websocket.send_json(
                    {
                        "type": "transcription",
                        "text": text,
                        "confidence": result.get("confidence", 0.0),
                        "language": result.get("language", "zh"),
                        "duration": session["buffer_duration"] if session else 0.0,
                        "asr_time": asr_time,
                        "timestamp": time.time(),
                    }
                )

                logger.info(
                    f"[Session {session_id}] ASR result: '{text}' "
                    f"(confidence={result.get('confidence', 0):.2f}, "
                    f"asr_time={asr_time*1000:.0f}ms)"
                )
            else:
                logger.debug(f"[Session {session_id}] ASR returned empty text")

        except Exception as e:
            logger.error(f"[Session {session_id}] ASR failed: {e}", exc_info=True)
            try:
                await websocket.send_json(
                    {"type": "error", "message": f"ASR failed: {str(e)}"}
                )
            except:
                pass

    async def _send_heartbeats(self, websocket: WebSocket, session_id: str):
        """
        发送心跳

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
        """
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                session = self.sessions.get(session_id)
                if not session:
                    break

                try:
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "buffer_duration": session["buffer_duration"],
                            "total_frames": session["total_frames"],
                            "recognition_count": session["recognition_count"],
                            "is_speaking": session["is_speaking"],
                            "timestamp": time.time(),
                        }
                    )
                except Exception as e:
                    logger.warning(f"[Session {session_id}] Heartbeat send failed: {e}")
                    break

        except asyncio.CancelledError:
            logger.debug(f"[Session {session_id}] Heartbeat task cancelled")
            raise

    async def _check_timeout(self, websocket: WebSocket, session_id: str):
        """
        检查会话超时

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
        """
        try:
            while True:
                await asyncio.sleep(10.0)  # 每10秒检查一次

                session = self.sessions.get(session_id)
                if not session:
                    break

                inactive_time = time.time() - session["last_activity_time"]
                if inactive_time > self.session_timeout:
                    logger.warning(
                        f"[Session {session_id}] Session timeout "
                        f"(inactive for {inactive_time:.1f}s)"
                    )

                    try:
                        await websocket.send_json(
                            {
                                "type": "timeout",
                                "message": "Session timeout due to inactivity",
                            }
                        )
                        await websocket.close(code=1000, reason="Session timeout")
                    except:
                        pass

                    break

        except asyncio.CancelledError:
            logger.debug(f"[Session {session_id}] Timeout check task cancelled")
            raise

    async def cleanup_session(self, session_id: str):
        """
        清理会话

        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            logger.info(
                f"[Session {session_id}] Cleanup: "
                f"total_frames={session['total_frames']}, "
                f"recognition_count={session['recognition_count']}"
            )
            del self.sessions[session_id]

    def get_session_count(self) -> int:
        """获取当前会话数"""
        return len(self.sessions)

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)
