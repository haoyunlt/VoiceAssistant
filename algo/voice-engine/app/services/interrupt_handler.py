"""
全双工打断处理服务

支持实时语音对话中的打断检测和TTS播放控制
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class InterruptState(Enum):
    """打断状态"""

    IDLE = "idle"  # 空闲
    LISTENING = "listening"  # 监听中
    SPEAKING = "speaking"  # 播放中
    INTERRUPTED = "interrupted"  # 已打断


class InterruptHandler:
    """打断处理器"""

    def __init__(
        self,
        interrupt_threshold: float = 0.5,  # 打断阈值（VAD概率）
        interrupt_duration: float = 0.3,  # 持续时间（秒）
        cooldown_period: float = 1.0,  # 冷却时间（秒）
    ):
        """
        初始化打断处理器

        Args:
            interrupt_threshold: VAD概率阈值，超过此值认为有语音
            interrupt_duration: 连续检测到语音的最小时长
            cooldown_period: 打断后的冷却时间
        """
        self.interrupt_threshold = interrupt_threshold
        self.interrupt_duration = interrupt_duration
        self.cooldown_period = cooldown_period

        self.state = InterruptState.IDLE
        self.last_interrupt_time = 0
        self.speech_start_time = None
        self.tts_playback = None

    def start_speaking(self, playback_control=None):
        """
        开始播放TTS

        Args:
            playback_control: TTS播放控制对象（需要有stop()方法）
        """
        self.state = InterruptState.SPEAKING
        self.tts_playback = playback_control
        logger.info("开始TTS播放")

    def stop_speaking(self):
        """停止播放TTS"""
        if self.state == InterruptState.SPEAKING:
            self.state = InterruptState.IDLE
            logger.info("TTS播放结束")

    def check_interrupt(self, vad_probability: float) -> bool:
        """
        检查是否应该打断

        Args:
            vad_probability: VAD检测到的语音概率

        Returns:
            是否应该打断
        """
        current_time = time.time()

        # 如果不在播放状态，不需要检查打断
        if self.state != InterruptState.SPEAKING:
            return False

        # 检查冷却时间
        if current_time - self.last_interrupt_time < self.cooldown_period:
            return False

        # 检测语音开始
        if vad_probability > self.interrupt_threshold:
            if self.speech_start_time is None:
                self.speech_start_time = current_time
                logger.debug("检测到用户语音开始")
            else:
                # 检查持续时长
                speech_duration = current_time - self.speech_start_time
                if speech_duration >= self.interrupt_duration:
                    logger.info(
                        f"检测到打断 (VAD={vad_probability:.2f}, duration={speech_duration:.2f}s)"
                    )
                    return True
        else:
            # 重置语音开始时间
            self.speech_start_time = None

        return False

    def handle_interrupt(self):
        """
        处理打断事件

        - 停止TTS播放
        - 更新状态
        - 记录打断时间
        """
        logger.info("处理打断事件")

        # 停止TTS播放
        if self.tts_playback and hasattr(self.tts_playback, "stop"):
            try:
                self.tts_playback.stop()
                logger.info("TTS播放已停止")
            except Exception as e:
                logger.error(f"停止TTS播放失败: {e}")

        # 更新状态
        self.state = InterruptState.INTERRUPTED
        self.last_interrupt_time = time.time()
        self.speech_start_time = None

    def reset(self):
        """重置状态"""
        self.state = InterruptState.IDLE
        self.speech_start_time = None
        self.tts_playback = None
        logger.debug("打断处理器已重置")


class FullDuplexHandler:
    """全双工对话处理器"""

    def __init__(
        self,
        vad_service,
        asr_service,
        tts_service,
        interrupt_handler: Optional[InterruptHandler] = None,
    ):
        """
        初始化全双工处理器

        Args:
            vad_service: VAD服务
            asr_service: ASR服务
            tts_service: TTS服务
            interrupt_handler: 打断处理器
        """
        self.vad_service = vad_service
        self.asr_service = asr_service
        self.tts_service = tts_service
        self.interrupt_handler = interrupt_handler or InterruptHandler()

        self.audio_buffer = bytearray()
        self.is_running = False
        self.tts_task = None

    async def start_listening(self):
        """开始监听"""
        self.is_running = True
        self.interrupt_handler.state = InterruptState.LISTENING
        logger.info("开始全双工监听")

    async def stop_listening(self):
        """停止监听"""
        self.is_running = False
        if self.tts_task:
            self.tts_task.cancel()
        logger.info("停止全双工监听")

    async def process_audio_frame(self, audio_data: bytes, sample_rate: int = 16000):
        """
        处理音频帧

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            处理结果（可能包含ASR文本或打断事件）
        """
        import numpy as np

        # 追加到缓冲区
        self.audio_buffer.extend(audio_data)

        # 转换为numpy数组
        audio_array = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16).astype(
            np.float32
        )
        audio_array = audio_array / 32768.0

        # VAD检测
        vad_prob = await self.vad_service.detect_speech(audio_array, sample_rate)

        result = {"type": "vad", "probability": vad_prob, "interrupted": False}

        # 检查是否打断
        if self.interrupt_handler.check_interrupt(vad_prob):
            self.interrupt_handler.handle_interrupt()
            result["type"] = "interrupt"
            result["interrupted"] = True

            # 清空缓冲区
            self.audio_buffer.clear()

            return result

        # 如果检测到语音结束，触发ASR
        if self.interrupt_handler.state == InterruptState.LISTENING:
            if vad_prob < 0.3 and len(self.audio_buffer) > sample_rate:  # 至少1秒
                # 触发ASR
                text = await self.asr_service.transcribe(bytes(self.audio_buffer))

                result["type"] = "transcription"
                result["text"] = text

                # 清空缓冲区
                self.audio_buffer.clear()

        return result

    async def speak_with_interrupt_detection(
        self, text: str, on_interrupt_callback=None
    ):
        """
        播放TTS，支持打断检测

        Args:
            text: 要播放的文本
            on_interrupt_callback: 打断时的回调函数
        """
        try:
            # 开始播放
            self.interrupt_handler.start_speaking()

            # 生成TTS音频（这里简化处理，实际应该是流式）
            audio_bytes = await self.tts_service.synthesize_to_bytes(text)

            # 模拟播放（实际应该发送到客户端）
            logger.info(f"播放TTS: {text[:50]}...")

            # 播放期间持续检查打断
            play_duration = len(audio_bytes) / (16000 * 2)  # 假设16kHz, 16bit
            check_interval = 0.1  # 每100ms检查一次

            for _ in range(int(play_duration / check_interval)):
                await asyncio.sleep(check_interval)

                # 检查是否被打断
                if self.interrupt_handler.state == InterruptState.INTERRUPTED:
                    logger.info("TTS播放被打断")
                    if on_interrupt_callback:
                        await on_interrupt_callback()
                    break

            # 播放结束
            self.interrupt_handler.stop_speaking()

        except asyncio.CancelledError:
            logger.info("TTS播放任务被取消")
            self.interrupt_handler.handle_interrupt()
        except Exception as e:
            logger.error(f"TTS播放失败: {e}", exc_info=True)
            self.interrupt_handler.stop_speaking()


class TTSPlaybackControl:
    """TTS播放控制（用于打断）"""

    def __init__(self):
        self.is_playing = False
        self.stop_event = asyncio.Event()

    def start(self):
        """开始播放"""
        self.is_playing = True
        self.stop_event.clear()

    def stop(self):
        """停止播放"""
        self.is_playing = False
        self.stop_event.set()
        logger.info("TTS播放控制：停止")

    async def wait_for_stop(self):
        """等待停止信号"""
        await self.stop_event.wait()


# 全局实例管理
_interrupt_handlers = {}


def get_interrupt_handler(session_id: str) -> InterruptHandler:
    """获取打断处理器实例"""
    if session_id not in _interrupt_handlers:
        _interrupt_handlers[session_id] = InterruptHandler()
    return _interrupt_handlers[session_id]


def remove_interrupt_handler(session_id: str):
    """移除打断处理器实例"""
    if session_id in _interrupt_handlers:
        del _interrupt_handlers[session_id]
