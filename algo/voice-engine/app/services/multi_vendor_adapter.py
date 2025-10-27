"""
Multi-Vendor Speech Adapter

多厂商语音服务适配器，支持：
- Edge TTS (免费, 默认)
- Azure Speech (付费, 高质量)
- Faster-Whisper ASR (本地, 免费)

自动降级策略：
ASR: Azure -> Faster-Whisper
TTS: Azure -> Edge TTS
"""

import os
from typing import Literal, Optional

import logging
from app.services.asr_service import ASRService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)


class MultiVendorSpeechAdapter:
    """多厂商语音适配器"""

    def __init__(
        self,
        preferred_asr: Literal["azure", "faster-whisper"] = "faster-whisper",
        preferred_tts: Literal["azure", "edge"] = "edge",
        azure_key: Optional[str] = None,
        azure_region: str = "eastasia",
    ):
        """
        初始化多厂商适配器

        Args:
            preferred_asr: 首选 ASR 服务（azure | faster-whisper）
            preferred_tts: 首选 TTS 服务（azure | edge）
            azure_key: Azure Speech 订阅密钥
            azure_region: Azure 区域
        """
        self.preferred_asr = preferred_asr
        self.preferred_tts = preferred_tts
        self.azure_key = azure_key or os.getenv("AZURE_SPEECH_KEY")
        self.azure_region = azure_region or os.getenv("AZURE_SPEECH_REGION", "eastasia")

        # 初始化服务
        self.edge_tts_service = TTSService()
        self.faster_whisper_service = ASRService()
        self.azure_service = None

        # 尝试初始化 Azure 服务
        if self.azure_key:
            try:
                from app.services.azure_speech_service import AzureSpeechService

                self.azure_service = AzureSpeechService(
                    subscription_key=self.azure_key, region=self.azure_region
                )
                logger.info("Azure Speech Service initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Azure Speech: {e}")
                self.azure_service = None
        else:
            logger.info("Azure Speech not configured (missing AZURE_SPEECH_KEY)")

        logger.info(
            f"Multi-vendor adapter initialized: ASR={preferred_asr}, TTS={preferred_tts}"
        )

    async def recognize(
        self, audio_data: bytes, language: str = "zh", model_size: str = "base"
    ) -> dict:
        """
        ASR 识别（自动降级）

        降级策略：
        1. 如果 preferred_asr == "azure" 且 Azure 可用 -> Azure
        2. 否则 -> Faster-Whisper

        Args:
            audio_data: 音频数据
            language: 语言代码
            model_size: Faster-Whisper 模型大小

        Returns:
            识别结果字典:
            {
                "text": str,
                "confidence": float,
                "language": str,
                "vendor": str,  # "azure" | "faster-whisper"
                "error": str (optional)
            }
        """
        # 策略 1: 尝试 Azure
        if self.preferred_asr == "azure" and self.azure_service:
            try:
                # Azure 语言代码映射
                azure_lang = self._map_language_to_azure(language)

                result = await self.azure_service.recognize_from_bytes(
                    audio_data, azure_lang
                )

                # 检查是否成功
                if "error" not in result or not result["error"]:
                    result["vendor"] = "azure"
                    logger.info("ASR succeeded with Azure")
                    return result
                else:
                    logger.warning(f"Azure ASR failed: {result.get('error')}, falling back to Faster-Whisper")

            except Exception as e:
                logger.warning(f"Azure ASR error: {e}, falling back to Faster-Whisper")

        # 策略 2: 使用 Faster-Whisper（降级）
        try:
            # Faster-Whisper 语言代码映射
            whisper_lang = self._map_language_to_whisper(language)

            result = await self.faster_whisper_service.recognize(
                audio_data, language=whisper_lang, model_size=model_size
            )

            result["vendor"] = "faster-whisper"
            logger.info("ASR succeeded with Faster-Whisper")
            return result

        except Exception as e:
            logger.error(f"Faster-Whisper ASR failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "vendor": "none",
                "error": f"所有 ASR 服务均失败: {str(e)}",
            }

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: str = "0%",
        pitch: str = "0%",
        use_cache: bool = True,
    ) -> tuple[bytes, str]:
        """
        TTS 合成（自动降级）

        降级策略：
        1. 如果 preferred_tts == "azure" 且 Azure 可用 -> Azure
        2. 否则 -> Edge TTS

        Args:
            text: 待合成文本
            voice: 语音名称（None 时使用默认）
            rate: 语速
            pitch: 音调
            use_cache: 是否使用缓存

        Returns:
            (音频数据, 厂商名称)
        """
        # 策略 1: 尝试 Azure
        if self.preferred_tts == "azure" and self.azure_service:
            try:
                # Azure 语音名称（如果未指定，使用默认）
                azure_voice = voice if voice and "Neural" in voice else "zh-CN-XiaoxiaoNeural"

                audio_data = await self.azure_service.synthesize(
                    text=text,
                    voice=azure_voice,
                    rate=rate,
                    pitch=pitch,
                )

                logger.info("TTS succeeded with Azure")
                return audio_data, "azure"

            except Exception as e:
                logger.warning(f"Azure TTS failed: {e}, falling back to Edge TTS")

        # 策略 2: 使用 Edge TTS（降级）
        try:
            # Edge 语音名称（如果未指定，使用默认）
            edge_voice = voice if voice and not voice.endswith("Neural") else "zh-CN-XiaoxiaoNeural"

            audio_data = await self.edge_tts_service.synthesize(
                text=text,
                voice=edge_voice,
                rate=rate,
                pitch=pitch,
                use_cache=use_cache,
            )

            logger.info("TTS succeeded with Edge TTS")
            return audio_data, "edge"

        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            raise Exception(f"所有 TTS 服务均失败: {str(e)}")

    def list_voices(self, vendor: Literal["azure", "edge", "all"] = "all") -> list:
        """
        列出可用的语音

        Args:
            vendor: 厂商筛选（azure | edge | all）

        Returns:
            语音列表
        """
        voices = []

        if vendor in ("azure", "all") and self.azure_service:
            azure_voices = self.azure_service.list_voices()
            for v in azure_voices:
                v["vendor"] = "azure"
            voices.extend(azure_voices)

        if vendor in ("edge", "all"):
            edge_voices = self.edge_tts_service.list_voices()
            for v in edge_voices:
                v["vendor"] = "edge"
            voices.extend(edge_voices)

        return voices

    def get_status(self) -> dict:
        """
        获取所有服务的状态

        Returns:
            状态字典
        """
        status = {
            "preferred_asr": self.preferred_asr,
            "preferred_tts": self.preferred_tts,
            "services": {},
        }

        # Azure 状态
        if self.azure_service:
            health = self.azure_service.health_check()
            status["services"]["azure"] = health
        else:
            status["services"]["azure"] = {
                "healthy": False,
                "error": "Azure not configured or failed to initialize",
            }

        # Edge TTS 状态
        status["services"]["edge_tts"] = {
            "healthy": True,
            "note": "Edge TTS is always available (free)",
        }

        # Faster-Whisper 状态
        status["services"]["faster_whisper"] = {
            "healthy": True,
            "note": "Faster-Whisper is always available (local)",
        }

        return status

    def _map_language_to_azure(self, language: str) -> str:
        """
        映射语言代码到 Azure 格式

        Args:
            language: 通用语言代码（zh, en, ja, etc.）

        Returns:
            Azure 语言代码（zh-CN, en-US, etc.）
        """
        mapping = {
            "zh": "zh-CN",
            "en": "en-US",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "es": "es-ES",
            "fr": "fr-FR",
            "de": "de-DE",
            "ru": "ru-RU",
        }
        return mapping.get(language, language)

    def _map_language_to_whisper(self, language: str) -> str:
        """
        映射语言代码到 Faster-Whisper 格式

        Args:
            language: 通用语言代码（zh, en, ja, etc.）

        Returns:
            Whisper 语言代码（zh, en, ja, etc.）
        """
        # Faster-Whisper 使用简短的语言代码
        if language.startswith("zh-"):
            return "zh"
        elif language.startswith("en-"):
            return "en"
        elif language.startswith("ja-"):
            return "ja"
        elif language.startswith("ko-"):
            return "ko"
        else:
            return language


# 单例实例
_multi_vendor_adapter: Optional[MultiVendorSpeechAdapter] = None


def get_multi_vendor_adapter() -> MultiVendorSpeechAdapter:
    """
    获取多厂商适配器实例（单例）

    Returns:
        MultiVendorSpeechAdapter 实例
    """
    global _multi_vendor_adapter

    if _multi_vendor_adapter is None:
        # 从环境变量读取配置
        preferred_asr = os.getenv("PREFERRED_ASR", "faster-whisper")
        preferred_tts = os.getenv("PREFERRED_TTS", "edge")

        _multi_vendor_adapter = MultiVendorSpeechAdapter(
            preferred_asr=preferred_asr,  # type: ignore
            preferred_tts=preferred_tts,  # type: ignore
        )

    return _multi_vendor_adapter
