"""
TTS (Text-to-Speech) 引擎
支持多种 TTS 服务和流式合成
"""

import asyncio
import io
import logging
from collections.abc import Generator
from typing import Any

import edge_tts
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class TTSEngine:
    """TTS 引擎"""

    def __init__(
        self,
        provider: str = "edge_tts",
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ):
        """
        初始化 TTS 引擎

        Args:
            provider: TTS 提供商 (edge_tts, azure, google, elevenlabs)
            voice: 语音名称
            rate: 语速调整
            volume: 音量调整
            pitch: 音高调整
        """
        self.provider = provider
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

        logger.info(f"TTS engine initialized: provider={provider}, voice={voice}")

    async def synthesize(
        self, text: str, output_format: str = "audio-24khz-48kbitrate-mono-mp3"
    ) -> bytes:
        """
        合成语音（批处理模式）

        Args:
            text: 待合成文本
            output_format: 输出格式

        Returns:
            音频字节流
        """
        try:
            logger.info(f"Synthesizing text: {text[:100]}...")

            if self.provider == "edge_tts":
                return await self._synthesize_edge_tts(text, output_format)
            else:
                raise ValueError(f"Unsupported TTS provider: {self.provider}")

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise

    async def synthesize_stream(
        self, text: str, chunk_size: int = 1024
    ) -> Generator[bytes, None, None]:
        """
        流式合成语音

        Args:
            text: 待合成文本
            chunk_size: 块大小

        Yields:
            音频块
        """
        logger.info(f"Starting streaming synthesis: {text[:100]}...")

        if self.provider == "edge_tts":
            async for chunk in self._synthesize_edge_tts_stream(text):
                yield chunk
        else:
            # 对于不支持流式的提供商，先全量合成再分块发送
            audio_data = await self.synthesize(text)
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i : i + chunk_size]

    async def _synthesize_edge_tts(self, text: str, _output_format: str) -> bytes:
        """使用 Edge TTS 合成"""
        communicate = edge_tts.Communicate(
            text=text, voice=self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch
        )

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    async def _synthesize_edge_tts_stream(self, text: str) -> Generator[bytes, None, None]:
        """使用 Edge TTS 流式合成"""
        communicate = edge_tts.Communicate(
            text=text, voice=self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    async def batch_synthesize(self, texts: list[str]) -> list[bytes]:
        """
        批量合成

        Args:
            texts: 文本列表

        Returns:
            音频列表
        """
        tasks = [self.synthesize(text) for text in texts]
        results = await asyncio.gather(*tasks)
        return results

    def get_available_voices(self) -> list[dict[str, Any]]:
        """
        获取可用语音列表

        Returns:
            语音列表
        """
        if self.provider == "edge_tts":
            # Edge TTS 支持的中文语音
            return [
                {
                    "name": "zh-CN-XiaoxiaoNeural",
                    "gender": "Female",
                    "locale": "zh-CN",
                    "description": "晓晓 (女)",
                },
                {
                    "name": "zh-CN-XiaoyiNeural",
                    "gender": "Female",
                    "locale": "zh-CN",
                    "description": "晓伊 (女)",
                },
                {
                    "name": "zh-CN-YunjianNeural",
                    "gender": "Male",
                    "locale": "zh-CN",
                    "description": "云健 (男)",
                },
                {
                    "name": "zh-CN-YunxiNeural",
                    "gender": "Male",
                    "locale": "zh-CN",
                    "description": "云希 (男)",
                },
                {
                    "name": "zh-CN-YunxiaNeural",
                    "gender": "Male",
                    "locale": "zh-CN",
                    "description": "云夏 (男)",
                },
                {
                    "name": "zh-CN-YunyangNeural",
                    "gender": "Male",
                    "locale": "zh-CN",
                    "description": "云扬 (男)",
                },
                {
                    "name": "zh-CN-liaoning-XiaobeiNeural",
                    "gender": "Female",
                    "locale": "zh-CN-liaoning",
                    "description": "晓北 (辽宁女)",
                },
                {
                    "name": "zh-CN-shaanxi-XiaoniNeural",
                    "gender": "Female",
                    "locale": "zh-CN-shaanxi",
                    "description": "晓妮 (陕西女)",
                },
            ]
        return []

    def adjust_audio_properties(
        self,
        audio_data: bytes,
        speed: float = 1.0,
        volume_gain: float = 0.0,
        sample_rate: int = None,
    ) -> bytes:
        """
        调整音频属性

        Args:
            audio_data: 音频数据
            speed: 速度倍数
            volume_gain: 音量增益（dB）
            sample_rate: 目标采样率

        Returns:
            调整后的音频数据
        """
        try:
            # 加载音频
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            # 调整速度
            if speed != 1.0:
                audio = audio.speedup(playback_speed=speed)

            # 调整音量
            if volume_gain != 0.0:
                audio = audio + volume_gain

            # 调整采样率
            if sample_rate and audio.frame_rate != sample_rate:
                audio = audio.set_frame_rate(sample_rate)

            # 导出
            output = io.BytesIO()
            audio.export(output, format="mp3")
            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to adjust audio properties: {e}")
            return audio_data


class StreamingTTSSession:
    """流式 TTS 会话（用于全双工对话）"""

    def __init__(self, tts_engine: TTSEngine, buffer_size: int = 3):
        """
        初始化流式会话

        Args:
            tts_engine: TTS 引擎
            buffer_size: 缓冲区大小（句子数）
        """
        self.tts_engine = tts_engine
        self.buffer_size = buffer_size

        self.text_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.is_running = False

        logger.info(f"Streaming TTS session initialized: buffer_size={buffer_size}")

    async def start(self):
        """启动会话"""
        self.is_running = True
        asyncio.create_task(self._process_queue())
        logger.info("Streaming TTS session started")

    async def stop(self):
        """停止会话"""
        self.is_running = False
        logger.info("Streaming TTS session stopped")

    async def add_text(self, text: str):
        """
        添加待合成文本

        Args:
            text: 文本
        """
        await self.text_queue.put(text)

    async def get_audio(self) -> bytes:
        """
        获取合成的音频

        Returns:
            音频数据
        """
        return await self.audio_queue.get()

    async def _process_queue(self):
        """处理队列"""
        while self.is_running:
            try:
                # 获取文本
                text = await asyncio.wait_for(self.text_queue.get(), timeout=1.0)

                # 合成音频
                audio = await self.tts_engine.synthesize(text)

                # 添加到音频队列
                await self.audio_queue.put(audio)

            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing TTS queue: {e}")

    def split_into_sentences(self, text: str) -> list[str]:
        """
        将文本分割为句子（用于流式输出）

        Args:
            text: 文本

        Returns:
            句子列表
        """
        import re

        # 按标点分割
        sentences = re.split(r"([。！？\.\!\?]+)", text)

        # 重新组合
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else "")
            if sentence.strip():
                result.append(sentence.strip())

        return result


class VoiceCloner:
    """语音克隆（可选功能）"""

    def __init__(self, model_path: str | None = None):
        """
        初始化语音克隆器

        Args:
            model_path: 模型路径
        """
        self.model_path = model_path
        logger.info("Voice cloner initialized (placeholder)")

    def clone_voice(self, _reference_audio: bytes, _text: str) -> bytes:
        """
        克隆语音

        Args:
            reference_audio: 参考音频
            text: 待合成文本

        Returns:
            合成的音频
        """
        # TODO: 实现语音克隆（使用 YourTTS, Coqui TTS 等）
        logger.warning("Voice cloning not implemented yet")
        raise NotImplementedError("Voice cloning is not implemented")
