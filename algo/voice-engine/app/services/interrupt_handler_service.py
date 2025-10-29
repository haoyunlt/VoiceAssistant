"""
全双工打断处理服务
实现实时打断检测和TTS播放控制
"""

import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class PlaybackState(str, Enum):
    """播放状态"""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"


class InterruptHandlerService:
    """打断处理服务"""

    def __init__(
        self,
        vad_service,
        interrupt_threshold: float = 0.5,
        interrupt_duration: float = 0.3,
    ):
        """
        初始化打断处理服务

        Args:
            vad_service: VAD语音检测服务
            interrupt_threshold: 打断检测阈值（语音概率）
            interrupt_duration: 持续多久被视为打断（秒）
        """
        self.vad_service = vad_service
        self.interrupt_threshold = interrupt_threshold
        self.interrupt_duration = interrupt_duration

        # 会话管理
        self.sessions: dict[str, dict] = {}

        logger.info(
            f"InterruptHandlerService initialized: "
            f"threshold={interrupt_threshold}, duration={interrupt_duration}s"
        )

    def create_session(self, session_id: str) -> dict:
        """
        创建会话

        Args:
            session_id: 会话ID

        Returns:
            会话信息
        """
        session = {
            "session_id": session_id,
            "playback_state": PlaybackState.IDLE,
            "tts_audio_queue": asyncio.Queue(),
            "interrupt_detected": False,
            "interrupt_time": None,
            "speech_start_time": None,
            "continuous_speech_duration": 0.0,
            "created_at": time.time(),
        }

        self.sessions[session_id] = session
        logger.info(f"Session {session_id} created")

        return session

    def get_session(self, session_id: str) -> dict | None:
        """获取会话"""
        return self.sessions.get(session_id)

    async def detect_interrupt(
        self, session_id: str, audio_chunk: bytes, sample_rate: int = 16000
    ) -> bool:
        """
        检测是否有打断

        Args:
            session_id: 会话ID
            audio_chunk: 音频块（用户语音）
            sample_rate: 采样率

        Returns:
            是否检测到打断
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return False

        # 只在播放状态检测打断
        if session["playback_state"] != PlaybackState.PLAYING:
            return False

        try:
            # VAD检测语音活动
            import numpy as np

            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(
                np.float32
            ) / 32768.0

            speech_prob = await self.vad_service.detect_speech(
                audio_array, sample_rate
            )

            current_time = time.time()

            # 语音活动开始
            if speech_prob > self.interrupt_threshold:
                if session["speech_start_time"] is None:
                    session["speech_start_time"] = current_time
                    logger.debug(f"Session {session_id}: Speech activity started")

                # 计算持续时长
                duration = current_time - session["speech_start_time"]
                session["continuous_speech_duration"] = duration

                # 判断是否达到打断阈值
                if duration >= self.interrupt_duration:
                    if not session["interrupt_detected"]:
                        session["interrupt_detected"] = True
                        session["interrupt_time"] = current_time
                        session["playback_state"] = PlaybackState.INTERRUPTED

                        logger.info(
                            f"Session {session_id}: Interrupt detected after {duration:.2f}s"
                        )

                        return True

            # 语音活动结束
            else:
                if session["speech_start_time"] is not None:
                    logger.debug(
                        f"Session {session_id}: Speech activity ended "
                        f"(duration={session['continuous_speech_duration']:.2f}s)"
                    )

                session["speech_start_time"] = None
                session["continuous_speech_duration"] = 0.0

            return session["interrupt_detected"]

        except Exception as e:
            logger.error(f"Failed to detect interrupt: {e}", exc_info=True)
            return False

    async def start_playback(
        self, session_id: str, tts_audio: bytes
    ) -> bool:
        """
        开始TTS播放

        Args:
            session_id: 会话ID
            tts_audio: TTS音频数据

        Returns:
            是否成功开始
        """
        session = self.get_session(session_id)
        if not session:
            return False

        try:
            # 清空队列
            while not session["tts_audio_queue"].empty():
                session["tts_audio_queue"].get_nowait()

            # 添加音频到队列
            await session["tts_audio_queue"].put(tts_audio)

            # 更新状态
            session["playback_state"] = PlaybackState.PLAYING
            session["interrupt_detected"] = False
            session["interrupt_time"] = None

            logger.info(f"Session {session_id}: TTS playback started")

            return True

        except Exception as e:
            logger.error(f"Failed to start playback: {e}")
            return False

    async def pause_playback(self, session_id: str) -> bool:
        """
        暂停播放

        Args:
            session_id: 会话ID

        Returns:
            是否成功暂停
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if session["playback_state"] == PlaybackState.PLAYING:
            session["playback_state"] = PlaybackState.PAUSED
            logger.info(f"Session {session_id}: Playback paused")
            return True

        return False

    async def resume_playback(self, session_id: str) -> bool:
        """
        恢复播放

        Args:
            session_id: 会话ID

        Returns:
            是否成功恢复
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if session["playback_state"] == PlaybackState.PAUSED:
            session["playback_state"] = PlaybackState.PLAYING
            logger.info(f"Session {session_id}: Playback resumed")
            return True

        return False

    async def stop_playback(self, session_id: str) -> bool:
        """
        停止播放（由于打断）

        Args:
            session_id: 会话ID

        Returns:
            是否成功停止
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # 清空队列
        while not session["tts_audio_queue"].empty():
            try:
                session["tts_audio_queue"].get_nowait()
            except asyncio.QueueEmpty:
                break

        session["playback_state"] = PlaybackState.IDLE
        session["interrupt_detected"] = False

        logger.info(f"Session {session_id}: Playback stopped")

        return True

    def get_playback_state(self, session_id: str) -> PlaybackState | None:
        """
        获取播放状态

        Args:
            session_id: 会话ID

        Returns:
            播放状态
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return session["playback_state"]

    async def handle_interrupt(self, session_id: str) -> dict:
        """
        处理打断事件

        Args:
            session_id: 会话ID

        Returns:
            处理结果
        """
        session = self.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        try:
            # 停止当前播放
            await self.stop_playback(session_id)

            # 重置打断标志
            session["interrupt_detected"] = False
            session["speech_start_time"] = None
            session["continuous_speech_duration"] = 0.0

            return {
                "success": True,
                "action": "interrupted",
                "session_id": session_id,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Failed to handle interrupt: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_session(self, session_id: str):
        """
        清理会话

        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            # 停止播放
            await self.stop_playback(session_id)

            # 删除会话
            del self.sessions[session_id]

            logger.info(f"Session {session_id} cleaned up")

    def get_statistics(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息
        """
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": sum(
                1
                for s in self.sessions.values()
                if s["playback_state"] == PlaybackState.PLAYING
            ),
            "interrupted_sessions": sum(
                1
                for s in self.sessions.values()
                if s["playback_state"] == PlaybackState.INTERRUPTED
            ),
        }
