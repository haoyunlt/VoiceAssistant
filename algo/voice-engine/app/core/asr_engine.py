"""
ASR Engine - 自动语音识别引擎（Whisper）
"""

import io
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class ASREngine:
    """ASR 引擎（基于 Whisper）"""

    def __init__(self):
        """初始化 ASR 引擎"""
        self.model = None
        self.model_name = "base"
        logger.info("ASR engine created")

    async def initialize(self):
        """初始化 Whisper 模型"""
        try:
            import whisper

            # 加载默认模型
            self.model = whisper.load_model(self.model_name)
            logger.info(f"Whisper model '{self.model_name}' loaded successfully")

        except ImportError:
            logger.warning("Whisper not installed. Using mock implementation.")
            self.model = None

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh",
        model: str = "base",
    ) -> Dict:
        """
        转录音频

        Args:
            audio_data: 音频数据
            language: 语言代码
            model: 模型名称

        Returns:
            转录结果
        """
        start_time = time.time()

        # 如果请求的模型与当前模型不同，重新加载
        if model != self.model_name:
            await self._load_model(model)

        try:
            if self.model is None:
                # Mock 实现
                return self._mock_transcribe(audio_data, language)

            # 将音频数据转换为临时文件
            audio_file = io.BytesIO(audio_data)

            # 执行转录
            result = self.model.transcribe(
                audio_file,
                language=language if language != "auto" else None,
            )

            duration = time.time() - start_time

            return {
                "text": result["text"],
                "language": result.get("language", language),
                "duration": duration,
                "segments": [
                    {
                        "text": seg["text"],
                        "start": seg["start"],
                        "end": seg["end"],
                    }
                    for seg in result.get("segments", [])
                ],
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise

    async def _load_model(self, model_name: str):
        """加载指定模型"""
        if self.model is None:
            return

        try:
            import whisper

            self.model = whisper.load_model(model_name)
            self.model_name = model_name
            logger.info(f"Whisper model switched to '{model_name}'")

        except Exception as e:
            logger.error(f"Failed to load model '{model_name}': {e}")
            raise

    def _mock_transcribe(self, audio_data: bytes, language: str) -> Dict:
        """Mock 转录（用于测试）"""
        return {
            "text": "这是模拟的语音识别结果",
            "language": language,
            "duration": 0.1,
            "segments": [
                {
                    "text": "这是模拟的语音识别结果",
                    "start": 0.0,
                    "end": 2.0,
                }
            ],
        }

    async def cleanup(self):
        """清理资源"""
        if self.model:
            del self.model
            self.model = None
        logger.info("ASR engine cleaned up")
