"""Azure Speech SDK集成服务"""
import logging
from typing import Optional, AsyncIterator
import io

logger = logging.getLogger(__name__)


class AzureSpeechService:
    """
    Azure Speech SDK服务
    
    作为Faster-Whisper和Edge-TTS的备份方案
    """

    def __init__(self, subscription_key: str, region: str):
        """
        初始化Azure Speech服务
        
        Args:
            subscription_key: Azure订阅密钥
            region: Azure区域（如'eastus'）
        """
        self.subscription_key = subscription_key
        self.region = region
        self.speech_config = None
        self.initialized = False

    async def initialize(self):
        """初始化Azure Speech SDK"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 配置Speech SDK
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            
            # 设置语音识别语言
            self.speech_config.speech_recognition_language = "zh-CN"
            
            # 设置语音合成语言和音色
            self.speech_config.speech_synthesis_language = "zh-CN"
            self.speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            
            self.initialized = True
            logger.info("Azure Speech Service initialized successfully")
            
        except ImportError:
            logger.warning("Azure Speech SDK not installed. Install with: pip install azure-cognitiveservices-speech")
            self.initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize Azure Speech Service: {e}")
            self.initialized = False

    async def recognize_from_bytes(
        self,
        audio_data: bytes,
        language: str = "zh-CN"
    ) -> dict:
        """
        从音频字节数据识别语音（ASR）
        
        Args:
            audio_data: 音频数据（WAV格式，16kHz，单声道）
            language: 识别语言
            
        Returns:
            识别结果字典
        """
        if not self.initialized:
            raise RuntimeError("Azure Speech Service not initialized")
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 创建音频流
            audio_stream = speechsdk.audio.PushAudioInputStream()
            audio_stream.write(audio_data)
            audio_stream.close()
            
            # 创建音频配置
            audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
            
            # 设置识别语言
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = language
            
            # 创建识别器
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )
            
            # 执行识别
            result = speech_recognizer.recognize_once()
            
            # 处理结果
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return {
                    "success": True,
                    "text": result.text,
                    "confidence": 0.95,  # Azure不提供置信度，使用固定值
                    "language": language,
                    "duration": 0,  # Azure不提供时长信息
                    "provider": "azure"
                }
            elif result.reason == speechsdk.ResultReason.NoMatch:
                return {
                    "success": False,
                    "text": "",
                    "error": "No speech recognized",
                    "provider": "azure"
                }
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                return {
                    "success": False,
                    "text": "",
                    "error": f"Recognition canceled: {cancellation.reason}",
                    "provider": "azure"
                }
            else:
                return {
                    "success": False,
                    "text": "",
                    "error": "Unknown error",
                    "provider": "azure"
                }
                
        except Exception as e:
            logger.error(f"Azure ASR error: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e),
                "provider": "azure"
            }

    async def recognize_streaming(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = "zh-CN"
    ) -> AsyncIterator[dict]:
        """
        流式语音识别
        
        Args:
            audio_stream: 音频流
            language: 识别语言
            
        Yields:
            识别结果字典
        """
        if not self.initialized:
            raise RuntimeError("Azure Speech Service not initialized")
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 创建推送流
            push_stream = speechsdk.audio.PushAudioInputStream()
            
            # 创建音频配置
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
            
            # 设置识别语言
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            speech_config.speech_recognition_language = language
            
            # 创建识别器
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )
            
            # 设置识别事件处理
            recognized_texts = []
            
            def recognized_callback(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    recognized_texts.append({
                        "text": evt.result.text,
                        "is_final": True,
                        "provider": "azure"
                    })
            
            speech_recognizer.recognized.connect(recognized_callback)
            
            # 开始连续识别
            speech_recognizer.start_continuous_recognition()
            
            # 推送音频数据
            async for chunk in audio_stream:
                push_stream.write(chunk)
                
                # 如果有识别结果，返回
                while recognized_texts:
                    yield recognized_texts.pop(0)
            
            # 关闭流
            push_stream.close()
            
            # 停止识别
            speech_recognizer.stop_continuous_recognition()
            
            # 返回剩余结果
            while recognized_texts:
                yield recognized_texts.pop(0)
                
        except Exception as e:
            logger.error(f"Azure streaming ASR error: {e}")
            yield {
                "text": "",
                "is_final": True,
                "error": str(e),
                "provider": "azure"
            }

    async def synthesize_to_bytes(
        self,
        text: str,
        voice_name: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "0%",
        pitch: str = "0%"
    ) -> bytes:
        """
        文本转语音（TTS）
        
        Args:
            text: 要合成的文本
            voice_name: 音色名称
            rate: 语速（-100%到+200%）
            pitch: 音调（-50%到+50%）
            
        Returns:
            音频数据（WAV格式）
        """
        if not self.initialized:
            raise RuntimeError("Azure Speech Service not initialized")
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 配置Speech SDK
            speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            
            # 设置音色
            speech_config.speech_synthesis_voice_name = voice_name
            
            # 创建音频配置（输出到内存）
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
            
            # 创建合成器
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=None  # None表示返回音频数据
            )
            
            # 构建SSML（用于控制语速和音调）
            ssml = f"""
            <speak version='1.0' xml:lang='zh-CN'>
                <voice name='{voice_name}'>
                    <prosody rate='{rate}' pitch='{pitch}'>
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            
            # 执行合成
            result = synthesizer.speak_ssml_async(ssml).get()
            
            # 处理结果
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                raise Exception(f"TTS canceled: {cancellation.reason}")
            else:
                raise Exception("TTS failed")
                
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            raise

    async def synthesize_streaming(
        self,
        text: str,
        voice_name: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "0%",
        pitch: str = "0%"
    ) -> AsyncIterator[bytes]:
        """
        流式文本转语音
        
        Args:
            text: 要合成的文本
            voice_name: 音色名称
            rate: 语速
            pitch: 音调
            
        Yields:
            音频数据块
        """
        if not self.initialized:
            raise RuntimeError("Azure Speech Service not initialized")
        
        try:
            # Azure SDK不直接支持流式输出，使用分块合成模拟
            # 将文本按句子分割
            sentences = self._split_sentences(text)
            
            for sentence in sentences:
                if sentence.strip():
                    audio_data = await self.synthesize_to_bytes(
                        text=sentence,
                        voice_name=voice_name,
                        rate=rate,
                        pitch=pitch
                    )
                    yield audio_data
                    
        except Exception as e:
            logger.error(f"Azure streaming TTS error: {e}")
            raise

    def _split_sentences(self, text: str) -> list:
        """将文本分割为句子"""
        import re
        # 按中文和英文句号分割
        sentences = re.split(r'[。！？.!?]', text)
        # 过滤空句子
        return [s.strip() for s in sentences if s.strip()]

    async def health_check(self) -> dict:
        """健康检查"""
        if not self.initialized:
            return {
                "healthy": False,
                "provider": "azure",
                "error": "Not initialized"
            }
        
        try:
            # 尝试简单的TTS来测试服务
            test_text = "测试"
            audio_data = await self.synthesize_to_bytes(test_text)
            
            return {
                "healthy": True,
                "provider": "azure",
                "test_audio_size": len(audio_data)
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": "azure",
                "error": str(e)
            }
