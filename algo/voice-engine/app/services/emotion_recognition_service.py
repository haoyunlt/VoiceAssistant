"""情感识别服务"""
import io
from typing import Dict

import librosa
import numpy as np
import torch
from pydantic import BaseModel
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

from app.core.config import settings
from app.core.logging import logger


class EmotionResult(BaseModel):
    """情感识别结果"""
    primary_emotion: str
    confidence: float
    all_emotions: Dict[str, float]


class EmotionRecognitionService:
    """情感识别服务"""

    def __init__(self):
        """初始化"""
        self.processor = None
        self.model = None
        self.emotions = ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]
        self._load_model()

    def _load_model(self):
        """加载情感识别模型"""
        try:
            model_name = settings.get(
                "EMOTION_MODEL",
                "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
            )

            # 加载processor和model
            self.processor = Wav2Vec2Processor.from_pretrained(model_name)
            self.model = Wav2Vec2ForSequenceClassification.from_pretrained(model_name)

            # 使用GPU（如果可用）
            if torch.cuda.is_available():
                self.model = self.model.to('cuda')

            # 设置为评估模式
            self.model.eval()

            logger.info(f"Emotion recognition model {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load emotion recognition model: {e}")

    async def recognize_emotion(
        self,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> EmotionResult:
        """识别语音情感

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            情感识别结果
        """
        if not self.processor or not self.model:
            raise RuntimeError("Emotion recognition model not loaded")

        try:
            # 1. 加载音频
            audio, sr = librosa.load(
                io.BytesIO(audio_data),
                sr=sample_rate,
                mono=True
            )

            # 2. 预处理
            inputs = self.processor(
                audio,
                sampling_rate=sample_rate,
                return_tensors="pt",
                padding=True
            )

            # 移动到GPU
            if torch.cuda.is_available():
                inputs = {k: v.to('cuda') for k, v in inputs.items()}

            # 3. 模型推理
            with torch.no_grad():
                logits = self.model(**inputs).logits
                predictions = torch.nn.functional.softmax(logits, dim=-1)

            # 移回CPU
            predictions = predictions.cpu().numpy()[0]

            # 4. 解析结果
            emotion_scores = {}
            for i, emotion in enumerate(self.emotions):
                emotion_scores[emotion] = float(predictions[i])

            # 获取主要情感
            primary_emotion_idx = np.argmax(predictions)
            primary_emotion = self.emotions[primary_emotion_idx]
            confidence = float(predictions[primary_emotion_idx])

            return EmotionResult(
                primary_emotion=primary_emotion,
                confidence=confidence,
                all_emotions=emotion_scores
            )
        except Exception as e:
            logger.error(f"Emotion recognition error: {e}")
            raise

    async def recognize_emotion_batch(
        self,
        audio_segments: list[bytes],
        sample_rate: int = 16000
    ) -> list[EmotionResult]:
        """批量识别情感

        Args:
            audio_segments: 音频片段列表
            sample_rate: 采样率

        Returns:
            情感识别结果列表
        """
        results = []

        for audio_data in audio_segments:
            try:
                result = await self.recognize_emotion(audio_data, sample_rate)
                results.append(result)
            except Exception as e:
                logger.error(f"Error recognizing emotion in segment: {e}")
                # 返回中性情感作为默认值
                results.append(EmotionResult(
                    primary_emotion="neutral",
                    confidence=0.5,
                    all_emotions={emotion: 0.125 for emotion in self.emotions}
                ))

        return results

    async def get_emotion_timeline(
        self,
        audio_data: bytes,
        segment_duration_ms: int = 3000,
        sample_rate: int = 16000
    ) -> list[dict]:
        """获取情感时间线

        Args:
            audio_data: 音频数据
            segment_duration_ms: 片段时长（毫秒）
            sample_rate: 采样率

        Returns:
            情感时间线
        """
        # 加载完整音频
        audio, sr = librosa.load(
            io.BytesIO(audio_data),
            sr=sample_rate,
            mono=True
        )

        # 计算片段样本数
        segment_samples = int(segment_duration_ms / 1000 * sample_rate)

        # 分割音频
        timeline = []
        for i in range(0, len(audio), segment_samples):
            segment_audio = audio[i:i + segment_samples]

            # 如果片段太短，跳过
            if len(segment_audio) < sample_rate * 0.5:  # 至少0.5秒
                continue

            # 转换为bytes
            import soundfile as sf
            output_buffer = io.BytesIO()
            sf.write(output_buffer, segment_audio, sample_rate, format='WAV')
            output_buffer.seek(0)
            segment_bytes = output_buffer.read()

            # 识别情感
            try:
                emotion_result = await self.recognize_emotion(segment_bytes, sample_rate)

                timeline.append({
                    "start_ms": i / sample_rate * 1000,
                    "end_ms": (i + len(segment_audio)) / sample_rate * 1000,
                    "emotion": emotion_result.primary_emotion,
                    "confidence": emotion_result.confidence,
                    "all_emotions": emotion_result.all_emotions
                })
            except Exception as e:
                logger.error(f"Error recognizing emotion for segment at {i}: {e}")

        return timeline

    def get_emotion_description(self, emotion: str, language: str = "zh") -> str:
        """获取情感描述

        Args:
            emotion: 情感标签
            language: 语言（zh/en）

        Returns:
            情感描述
        """
        descriptions_zh = {
            "angry": "愤怒",
            "calm": "平静",
            "disgust": "厌恶",
            "fearful": "恐惧",
            "happy": "开心",
            "neutral": "中性",
            "sad": "悲伤",
            "surprised": "惊讶"
        }

        descriptions_en = {
            "angry": "Angry",
            "calm": "Calm",
            "disgust": "Disgust",
            "fearful": "Fearful",
            "happy": "Happy",
            "neutral": "Neutral",
            "sad": "Sad",
            "surprised": "Surprised"
        }

        if language == "zh":
            return descriptions_zh.get(emotion, emotion)
        else:
            return descriptions_en.get(emotion, emotion)
