"""
Azure Speech Service

提供 Azure Cognitive Services Speech SDK 集成：
- ASR (Automatic Speech Recognition)
- TTS (Text-to-Speech)
"""

import os
from typing import Optional

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    speechsdk = None

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AzureSpeechService:
    """Azure 语音服务"""

    def __init__(
        self,
        subscription_key: Optional[str] = None,
        region: str = "eastasia",
    ):
        """
        初始化 Azure Speech 服务

        Args:
            subscription_key: Azure Speech 订阅密钥
            region: Azure 区域（默认 eastasia）

        Raises:
            ImportError: 如果 Azure SDK 未安装
            ValueError: 如果 subscription_key 未提供
        """
        if not AZURE_SDK_AVAILABLE:
            raise ImportError(
                "Azure Speech SDK not installed. "
                "Install it with: pip install azure-cognitiveservices-speech"
            )

        self.subscription_key = subscription_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = region or os.getenv("AZURE_SPEECH_REGION", "eastasia")

        if not self.subscription_key:
            raise ValueError(
                "Azure Speech subscription key is required. "
                "Set AZURE_SPEECH_KEY environment variable or pass it to constructor."
            )

        # ASR 配置
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key, region=self.region
        )

        logger.info(f"Azure Speech Service initialized (region: {self.region})")

    async def recognize_from_bytes(
        self, audio_data: bytes, language: str = "zh-CN"
    ) -> dict:
        """
        ASR 识别（从字节数据）

        Args:
            audio_data: 音频数据（16kHz, 16-bit, mono PCM）
            language: 语言代码（zh-CN, en-US 等）

        Returns:
            识别结果字典:
            {
                "text": str,          # 识别的文本
                "confidence": float,  # 置信度 (0-1)
                "language": str,      # 语言代码
                "duration_ms": float, # 音频时长（毫秒）
                "error": str          # 错误信息（如果失败）
            }
        """
        try:
            # 设置识别语言
            self.speech_config.speech_recognition_language = language

            # 创建音频格式
            audio_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=16000, bits_per_sample=16, channels=1
            )

            # 创建推送流
            push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
            push_stream.write(audio_data)
            push_stream.close()

            # 创建音频配置
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

            # 创建识别器
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, audio_config=audio_config
            )

            # 执行识别（同步）
            result = speech_recognizer.recognize_once()

            # 处理结果
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # 成功识别
                confidence = 0.0
                try:
                    # 尝试从 JSON 获取置信度
                    import json
                    result_json = json.loads(result.json)
                    if "NBest" in result_json and len(result_json["NBest"]) > 0:
                        confidence = result_json["NBest"][0].get("Confidence", 0.0)
                except Exception:
                    confidence = 0.9  # 默认置信度

                duration_ms = 0
                if hasattr(result, "duration"):
                    duration_ms = result.duration.total_seconds() * 1000

                return {
                    "text": result.text,
                    "confidence": confidence,
                    "language": language,
                    "duration_ms": duration_ms,
                }

            elif result.reason == speechsdk.ResultReason.NoMatch:
                # 未识别到语音
                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": language,
                    "error": "未识别到语音内容",
                }

            elif result.reason == speechsdk.ResultReason.Canceled:
                # 识别被取消
                cancellation = result.cancellation_details
                error_msg = f"识别取消: {cancellation.reason}"
                if cancellation.error_details:
                    error_msg += f", {cancellation.error_details}"

                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": language,
                    "error": error_msg,
                }

            else:
                # 其他错误
                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": language,
                    "error": f"未知识别结果: {result.reason}",
                }

        except Exception as e:
            logger.error(f"Azure ASR failed: {e}", exc_info=True)
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "error": f"Azure ASR 错误: {str(e)}",
            }

    async def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "0%",
        pitch: str = "0%",
    ) -> bytes:
        """
        TTS 合成

        Args:
            text: 待合成文本
            voice: 语音名称（zh-CN-XiaoxiaoNeural 等）
            rate: 语速（-50% ~ +100%）
            pitch: 音调（-50% ~ +50%）

        Returns:
            音频数据（bytes）

        Raises:
            Exception: 合成失败
        """
        try:
            # 设置语音
            self.speech_config.speech_synthesis_voice_name = voice

            # 构建 SSML
            ssml = self._build_ssml(text, voice, rate, pitch)

            # 创建合成器（使用内存流）
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config, audio_config=None
            )

            # 执行合成
            result = synthesizer.speak_ssml_async(ssml).get()

            # 处理结果
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(
                    f"Azure TTS synthesis completed (length: {len(result.audio_data)} bytes)"
                )
                return result.audio_data

            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                error_msg = f"合成取消: {cancellation.reason}"
                if cancellation.error_details:
                    error_msg += f", {cancellation.error_details}"

                logger.error(error_msg)
                raise Exception(error_msg)

            else:
                error_msg = f"未知合成结果: {result.reason}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Azure TTS synthesis failed: {e}", exc_info=True)
            raise

    def _build_ssml(
        self, text: str, voice: str, rate: str = "0%", pitch: str = "0%"
    ) -> str:
        """
        构建 SSML

        Args:
            text: 文本
            voice: 语音名称
            rate: 语速
            pitch: 音调

        Returns:
            SSML 字符串
        """
        # 确定语言
        lang = "zh-CN" if voice.startswith("zh-") else "en-US"

        ssml = f"""
        <speak version='1.0' xml:lang='{lang}' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts'>
            <voice name='{voice}'>
                <prosody rate='{rate}' pitch='{pitch}'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        return ssml.strip()

    def list_voices(self) -> list:
        """
        列出可用的语音

        Returns:
            语音列表
        """
        # 常用的 Azure Neural 语音
        return [
            {
                "name": "zh-CN-XiaoxiaoNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓晓（女声，温暖友好）",
            },
            {
                "name": "zh-CN-YunxiNeural",
                "gender": "Male",
                "language": "zh-CN",
                "description": "云希（男声，自然稳重）",
            },
            {
                "name": "zh-CN-YunyangNeural",
                "gender": "Male",
                "language": "zh-CN",
                "description": "云扬（男声，新闻播报）",
            },
            {
                "name": "zh-CN-XiaoyiNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓伊（女声，温柔体贴）",
            },
            {
                "name": "zh-CN-YunjianNeural",
                "gender": "Male",
                "language": "zh-CN",
                "description": "云健（男声，运动解说）",
            },
            {
                "name": "zh-CN-XiaochenNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓辰（女声，活泼可爱）",
            },
            {
                "name": "zh-CN-XiaohanNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓涵（女声，亲切自然）",
            },
            {
                "name": "zh-CN-XiaomengNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓梦（女声，甜美温柔）",
            },
            {
                "name": "zh-CN-XiaomoNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓墨（女声，知性优雅）",
            },
            {
                "name": "zh-CN-XiaoqiuNeural",
                "gender": "Female",
                "language": "zh-CN",
                "description": "晓秋（女声，成熟稳重）",
            },
            # 英文语音
            {
                "name": "en-US-AriaNeural",
                "gender": "Female",
                "language": "en-US",
                "description": "Aria (Female, Newscast)",
            },
            {
                "name": "en-US-GuyNeural",
                "gender": "Male",
                "language": "en-US",
                "description": "Guy (Male, Newscast)",
            },
            {
                "name": "en-US-JennyNeural",
                "gender": "Female",
                "language": "en-US",
                "description": "Jenny (Female, Assistant)",
            },
            {
                "name": "en-US-DavisNeural",
                "gender": "Male",
                "language": "en-US",
                "description": "Davis (Male, Chat)",
            },
        ]

    def health_check(self) -> dict:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not AZURE_SDK_AVAILABLE:
            return {
                "healthy": False,
                "error": "Azure Speech SDK not installed",
            }

        if not self.subscription_key:
            return {
                "healthy": False,
                "error": "Azure Speech subscription key not configured",
            }

        return {
            "healthy": True,
            "region": self.region,
            "sdk_available": True,
        }
