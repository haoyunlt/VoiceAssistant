"""
全双工对话引擎
支持同时进行语音识别和合成，实现自然对话
"""

import asyncio
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

from app.core.asr_engine import ASREngine, VoiceActivityDetection
from app.core.tts_engine import StreamingTTSSession, TTSEngine

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """对话状态"""

    IDLE = "idle"  # 空闲
    LISTENING = "listening"  # 监听中
    PROCESSING = "processing"  # 处理中
    SPEAKING = "speaking"  # 说话中
    INTERRUPTED = "interrupted"  # 被打断


class FullDuplexEngine:
    """全双工对话引擎"""

    def __init__(
        self,
        asr_engine: ASREngine,
        tts_engine: TTSEngine,
        vad: VoiceActivityDetection,
        interrupt_threshold: float = 0.7,
        silence_timeout: float = 1.5,
    ):
        """
        初始化全双工引擎

        Args:
            asr_engine: ASR 引擎
            tts_engine: TTS 引擎
            vad: VAD 引擎
            interrupt_threshold: 打断阈值
            silence_timeout: 静音超时（秒）
        """
        self.asr_engine = asr_engine
        self.tts_engine = tts_engine
        self.vad = vad
        self.interrupt_threshold = interrupt_threshold
        self.silence_timeout = silence_timeout

        # 会话状态
        self.state = ConversationState.IDLE

        # TTS 会话
        self.tts_session = StreamingTTSSession(tts_engine)

        # 回调函数
        self.on_user_speech: Callable | None = None
        self.on_assistant_response: Callable | None = None
        self.on_state_change: Callable | None = None

        # 音频缓冲区
        self.audio_buffer = []
        self.silence_duration = 0.0

        logger.info("Full duplex engine initialized")

    async def start_conversation(self):
        """开始对话"""
        logger.info("Starting full duplex conversation")

        self._change_state(ConversationState.LISTENING)

        # 启动 TTS 会话
        await self.tts_session.start()

    async def stop_conversation(self):
        """停止对话"""
        logger.info("Stopping full duplex conversation")

        self._change_state(ConversationState.IDLE)

        # 停止 TTS 会话
        await self.tts_session.stop()

    async def process_audio_chunk(
        self, audio_chunk: bytes, sample_rate: int = 16000
    ) -> dict[str, Any]:
        """
        处理音频块（实时输入）

        Args:
            audio_chunk: 音频块
            sample_rate: 采样率

        Returns:
            处理结果
        """
        result = {
            "state": self.state.value,
            "has_speech": False,
            "transcription": None,
            "interrupted": False,
        }

        # 1. VAD 检测
        has_speech = self.vad.is_speech(audio_chunk, sample_rate)
        result["has_speech"] = has_speech

        # 2. 状态机处理
        if self.state == ConversationState.LISTENING:
            if has_speech:
                # 检测到语音，开始累积
                self.audio_buffer.append(audio_chunk)
                self.silence_duration = 0.0
            else:
                # 静音
                if self.audio_buffer:
                    # 已经有语音缓冲，累积静音
                    self.audio_buffer.append(audio_chunk)
                    self.silence_duration += len(audio_chunk) / sample_rate / 2

                    # 如果静音时间足够，触发 ASR
                    if self.silence_duration >= self.silence_timeout:
                        await self._process_speech()
                        result["transcription"] = self.last_transcription

        elif self.state == ConversationState.SPEAKING:  # noqa: SIM102
            # 检测打断
            if has_speech:
                speech_strength = self._calculate_speech_strength(audio_chunk)
                if speech_strength > self.interrupt_threshold:
                    logger.info("User interrupted assistant")
                    await self._handle_interruption()
                    result["interrupted"] = True

        return result

    async def _process_speech(self):
        """处理语音输入"""
        if not self.audio_buffer:
            return

        logger.info("Processing user speech")
        self._change_state(ConversationState.PROCESSING)

        # 合并音频
        combined_audio = b"".join(self.audio_buffer)

        # ASR 识别
        transcription_result = self.asr_engine.transcribe(combined_audio)
        transcription = transcription_result.get("text", "")

        logger.info(f"User said: {transcription}")
        self.last_transcription = transcription

        # 触发回调
        if self.on_user_speech:
            response = await self.on_user_speech(transcription)

            # 生成回复
            if response:
                await self._generate_response(response)

        # 重置缓冲区
        self.audio_buffer = []
        self.silence_duration = 0.0

        # 回到监听状态
        self._change_state(ConversationState.LISTENING)

    async def _generate_response(self, text: str):
        """生成回复"""
        logger.info(f"Generating response: {text[:100]}...")
        self._change_state(ConversationState.SPEAKING)

        # 分句
        sentences = self.tts_session.split_into_sentences(text)

        # 逐句合成和播放
        for sentence in sentences:
            if self.state != ConversationState.SPEAKING:
                # 被打断，停止生成
                break

            # 添加到 TTS 队列
            await self.tts_session.add_text(sentence)

            # 获取音频并触发回调
            audio = await self.tts_session.get_audio()

            if self.on_assistant_response:
                await self.on_assistant_response(audio)

    async def _handle_interruption(self):
        """处理打断"""
        logger.info("Handling interruption")
        self._change_state(ConversationState.INTERRUPTED)

        # 停止当前播放
        # TODO: 实际实现中需要停止音频播放

        # 清空 TTS 队列
        while not self.tts_session.text_queue.empty():
            try:
                self.tts_session.text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self.tts_session.audio_queue.empty():
            try:
                self.tts_session.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 回到监听状态
        self._change_state(ConversationState.LISTENING)

    def _calculate_speech_strength(self, audio_chunk: bytes) -> float:
        """
        计算语音强度

        Args:
            audio_chunk: 音频块

        Returns:
            语音强度 [0, 1]
        """
        import numpy as np

        # 转换为 numpy 数组
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

        # 计算 RMS（均方根）
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

        # 归一化到 [0, 1]
        normalized = min(rms / 10000.0, 1.0)

        return normalized

    def _change_state(self, new_state: ConversationState):
        """改变状态"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state

            logger.info(f"State changed: {old_state.value} -> {new_state.value}")

            # 触发回调
            if self.on_state_change:
                self.on_state_change(old_state, new_state)

    def set_callback(self, callback_name: str, callback: Callable):
        """
        设置回调函数

        Args:
            callback_name: 回调名称 (on_user_speech, on_assistant_response, on_state_change)
            callback: 回调函数
        """
        if callback_name == "on_user_speech":
            self.on_user_speech = callback
        elif callback_name == "on_assistant_response":
            self.on_assistant_response = callback
        elif callback_name == "on_state_change":
            self.on_state_change = callback
        else:
            logger.warning(f"Unknown callback: {callback_name}")


class ConversationMetrics:
    """对话指标"""

    def __init__(self):
        """初始化指标"""
        self.total_turns = 0
        self.total_interruptions = 0
        self.total_duration = 0.0
        self.average_response_time = 0.0
        self.user_speech_time = 0.0
        self.assistant_speech_time = 0.0

        self.turn_times = []
        self.response_times = []

    def record_turn(
        self, user_speech_duration: float, processing_time: float, assistant_speech_duration: float
    ):
        """记录一轮对话"""
        self.total_turns += 1
        self.user_speech_time += user_speech_duration
        self.assistant_speech_time += assistant_speech_duration

        response_time = processing_time
        self.response_times.append(response_time)
        self.average_response_time = sum(self.response_times) / len(self.response_times)

        turn_time = user_speech_duration + processing_time + assistant_speech_duration
        self.turn_times.append(turn_time)
        self.total_duration = sum(self.turn_times)

    def record_interruption(self):
        """记录打断"""
        self.total_interruptions += 1

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_turns": self.total_turns,
            "total_interruptions": self.total_interruptions,
            "total_duration": self.total_duration,
            "average_response_time": self.average_response_time,
            "user_speech_time": self.user_speech_time,
            "assistant_speech_time": self.assistant_speech_time,
            "user_speech_ratio": self.user_speech_time / self.total_duration
            if self.total_duration > 0
            else 0,
            "assistant_speech_ratio": self.assistant_speech_time / self.total_duration
            if self.total_duration > 0
            else 0,
        }
