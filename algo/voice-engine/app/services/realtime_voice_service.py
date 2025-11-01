"""
实时语音流服务
WebSocket双向通信 + 实时VAD触发ASR
"""

import asyncio
import builtins
import contextlib
import logging
import time

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
        max_concurrent_sessions: int = 100,
        max_buffer_size_bytes: int = 16 * 1024 * 1024,  # 16MB
        max_audio_duration_seconds: float = 60.0,
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
            max_concurrent_sessions: 最大并发会话数
            max_buffer_size_bytes: 单个会话最大缓冲区大小（字节）
            max_audio_duration_seconds: 单个音频片段最大时长（秒）
        """
        self.asr = asr_service
        self.vad = vad_service
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.min_speech_duration = min_speech_duration
        self.silence_duration = silence_duration
        self.heartbeat_interval = heartbeat_interval
        self.session_timeout = session_timeout

        # 资源限制
        self.max_concurrent_sessions = max_concurrent_sessions
        self.max_buffer_size_bytes = max_buffer_size_bytes
        self.max_audio_duration_seconds = max_audio_duration_seconds

        # 会话管理
        self.sessions: dict[str, dict] = {}

        # 统计信息
        self.total_sessions_created = 0
        self.total_sessions_rejected = 0
        self.total_buffer_overflows = 0

        logger.info(
            f"RealtimeVoiceService initialized: "
            f"sample_rate={sample_rate}, "
            f"vad_threshold={vad_threshold}, "
            f"min_speech_duration={min_speech_duration}, "
            f"max_concurrent_sessions={max_concurrent_sessions}, "
            f"max_buffer_size={max_buffer_size_bytes / 1024 / 1024:.1f}MB"
        )

    async def handle_stream(self, websocket: WebSocket, session_id: str):
        """
        处理WebSocket音频流（带资源限制）

        Args:
            websocket: WebSocket连接
            session_id: 会话ID
        """
        # 检查并发连接数限制
        if len(self.sessions) >= self.max_concurrent_sessions:
            self.total_sessions_rejected += 1
            logger.warning(
                f"Session {session_id} rejected: "
                f"max concurrent sessions ({self.max_concurrent_sessions}) reached. "
                f"Current sessions: {len(self.sessions)}"
            )
            await websocket.close(
                code=1008,
                reason=f"Server at maximum capacity ({self.max_concurrent_sessions} sessions)",
            )
            return

        # 初始化会话
        session = {
            "audio_buffer": bytearray(),
            "buffer_duration": 0.0,
            "is_speaking": False,
            "last_speech_time": 0.0,
            "last_activity_time": time.time(),
            "total_frames": 0,
            "recognition_count": 0,
            "buffer_overflow_count": 0,
        }
        self.sessions[session_id] = session
        self.total_sessions_created += 1

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(self._send_heartbeats(websocket, session_id))

        # 启动超时检测任务
        timeout_task = asyncio.create_task(self._check_timeout(websocket, session_id))

        try:
            logger.info(f"[Session {session_id}] Stream handling started")

            while True:
                # 接收音频数据（binary）
                data = await websocket.receive_bytes()

                # 更新活动时间
                session["last_activity_time"] = time.time()

                # 检查缓冲区大小限制
                buffer_size_after = len(session["audio_buffer"]) + len(data)
                if buffer_size_after > self.max_buffer_size_bytes:
                    session["buffer_overflow_count"] += 1
                    self.total_buffer_overflows += 1

                    logger.warning(
                        f"[Session {session_id}] Buffer overflow: "
                        f"size={buffer_size_after / 1024 / 1024:.2f}MB, "
                        f"limit={self.max_buffer_size_bytes / 1024 / 1024:.2f}MB. "
                        f"Triggering ASR early."
                    )

                    # 强制触发ASR以清空缓冲区
                    if len(session["audio_buffer"]) > 0:
                        await self._trigger_asr(
                            websocket, session_id, bytes(session["audio_buffer"])
                        )
                        session["audio_buffer"].clear()
                        session["buffer_duration"] = 0.0
                        session["is_speaking"] = False

                # 检查音频时长限制
                if session["buffer_duration"] > self.max_audio_duration_seconds:
                    logger.warning(
                        f"[Session {session_id}] Audio duration exceeded: "
                        f"{session['buffer_duration']:.1f}s > {self.max_audio_duration_seconds:.1f}s. "
                        f"Triggering ASR."
                    )

                    await self._trigger_asr(websocket, session_id, bytes(session["audio_buffer"]))
                    session["audio_buffer"].clear()
                    session["buffer_duration"] = 0.0
                    session["is_speaking"] = False

                session["audio_buffer"].extend(data)
                session["buffer_duration"] += len(data) / (self.sample_rate * 2)
                session["total_frames"] += 1

                # 转换音频数据为float32
                audio_array = (
                    np.frombuffer(bytes(session["audio_buffer"]), dtype=np.int16).astype(np.float32)
                    / 32768.0
                )

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
                            f"[Session {session_id}] Speech started (prob={speech_prob:.2f})"
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
            with contextlib.suppress(builtins.BaseException):
                await websocket.send_json({"type": "error", "message": f"Stream error: {str(e)}"})

        finally:
            # 取消后台任务
            heartbeat_task.cancel()
            timeout_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

            with contextlib.suppress(asyncio.CancelledError):
                await timeout_task

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

    async def _trigger_asr(self, websocket: WebSocket, session_id: str, audio_bytes: bytes):
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
                    f"asr_time={asr_time * 1000:.0f}ms)"
                )
            else:
                logger.debug(f"[Session {session_id}] ASR returned empty text")

        except Exception as e:
            logger.error(f"[Session {session_id}] ASR failed: {e}", exc_info=True)
            with contextlib.suppress(builtins.BaseException):
                await websocket.send_json({"type": "error", "message": f"ASR failed: {str(e)}"})

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
                    except Exception:
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

    def get_session_info(self, session_id: str) -> dict | None:
        """获取会话信息"""
        return self.sessions.get(session_id)

    def get_statistics(self) -> dict:
        """
        获取服务统计信息

        Returns:
            统计信息字典
        """
        return {
            "current_sessions": len(self.sessions),
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "utilization": len(self.sessions) / self.max_concurrent_sessions,
            "total_sessions_created": self.total_sessions_created,
            "total_sessions_rejected": self.total_sessions_rejected,
            "total_buffer_overflows": self.total_buffer_overflows,
            "rejection_rate": (
                self.total_sessions_rejected
                / max(self.total_sessions_created + self.total_sessions_rejected, 1)
            ),
            "max_buffer_size_mb": self.max_buffer_size_bytes / 1024 / 1024,
            "max_audio_duration_s": self.max_audio_duration_seconds,
        }
