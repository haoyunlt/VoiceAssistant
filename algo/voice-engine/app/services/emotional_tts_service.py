"""
Emotional TTS Service with Prosody Control
"""

import logging
import re
from collections.abc import AsyncIterator
from enum import Enum

logger = logging.getLogger(__name__)


class Emotion(Enum):
    """Emotion types"""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    GENTLE = "gentle"
    EXCITED = "excited"
    CALM = "calm"


class EmotionalTTSService:
    """Emotional TTS service with prosody control"""

    def __init__(self, tts_service, llm_client=None):
        self.tts_service = tts_service
        self.llm_client = llm_client
        self.emotion_cache = {}

    async def synthesize_with_emotion(
        self,
        text: str,
        emotion: Emotion | None = None,
        intensity: float = 0.5,
        auto_detect: bool = True,
    ) -> bytes:
        """Synthesize speech with emotion"""
        try:
            # 1. Detect emotion if not specified
            if emotion is None or (emotion == Emotion.NEUTRAL and auto_detect):
                emotion = await self._detect_emotion(text)
                logger.info(f"Detected emotion: {emotion.value}")
            else:
                logger.info(f"Using specified emotion: {emotion.value}")

            # 2. Generate emotional SSML
            ssml = self._generate_emotional_ssml(text, emotion, intensity)

            # 3. Synthesize
            audio = await self.tts_service.synthesize_ssml(ssml)

            return audio

        except Exception as e:
            logger.error(f"Emotional TTS synthesis failed: {e}")
            # Fallback to normal synthesis
            return await self.tts_service.synthesize_to_bytes(text)

    async def synthesize_streaming(
        self,
        text: str,
        emotion: Emotion | None = None,
        intensity: float = 0.5,
        auto_detect: bool = True,
    ) -> AsyncIterator[bytes]:
        """Synthesize speech with emotion (streaming)"""
        try:
            # 1. Detect emotion
            if emotion is None or (emotion == Emotion.NEUTRAL and auto_detect):
                emotion = await self._detect_emotion(text)

            # 2. Split into segments and synthesize
            segments = self._split_by_emotion_context(text)

            for segment_text, segment_emotion in segments:
                # Use segment-specific emotion or default
                current_emotion = segment_emotion or emotion

                # Generate SSML for segment
                ssml = self._generate_emotional_ssml(segment_text, current_emotion, intensity)

                # Synthesize segment
                async for audio_chunk in self.tts_service.synthesize_streaming(ssml):
                    yield audio_chunk

        except Exception as e:
            logger.error(f"Streaming emotional TTS failed: {e}")
            # Fallback
            async for chunk in self.tts_service.synthesize_streaming(text):
                yield chunk

    def _generate_emotional_ssml(self, text: str, emotion: Emotion, intensity: float) -> str:
        """Generate SSML with emotional prosody"""
        # Get emotion parameters
        params = self._get_emotion_parameters(emotion, intensity)

        # Build SSML
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
    xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>
    <voice name='{params["voice"]}'>
        <mstts:express-as style='{params["style"]}' styledegree='{intensity}'>
            <prosody rate='{params["rate"]}' pitch='{params["pitch"]}' volume='{params["volume"]}'>
                {self._escape_ssml(text)}
            </prosody>
        </mstts:express-as>
    </voice>
</speak>"""

        return ssml

    def _get_emotion_parameters(self, emotion: Emotion, intensity: float) -> dict[str, str]:
        """Get prosody parameters for emotion"""
        # Base parameters
        base_params = {
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "style": "general",
        }

        # Emotion-specific adjustments
        emotion_map = {
            Emotion.HAPPY: {
                "rate": f"+{int(10 * intensity)}%",
                "pitch": f"+{int(5 * intensity)}Hz",
                "volume": f"+{int(10 * intensity)}%",
                "style": "cheerful",
            },
            Emotion.SAD: {
                "rate": f"-{int(10 * intensity)}%",
                "pitch": f"-{int(5 * intensity)}Hz",
                "volume": f"-{int(5 * intensity)}%",
                "style": "sad",
            },
            Emotion.ANGRY: {
                "rate": f"+{int(5 * intensity)}%",
                "pitch": f"+{int(10 * intensity)}Hz",
                "volume": f"+{int(15 * intensity)}%",
                "style": "angry",
            },
            Emotion.GENTLE: {
                "rate": f"-{int(5 * intensity)}%",
                "pitch": "+0Hz",
                "volume": "+0%",
                "style": "gentle",
            },
            Emotion.EXCITED: {
                "rate": f"+{int(15 * intensity)}%",
                "pitch": f"+{int(8 * intensity)}Hz",
                "volume": f"+{int(12 * intensity)}%",
                "style": "excited",
            },
            Emotion.CALM: {
                "rate": f"-{int(8 * intensity)}%",
                "pitch": f"-{int(3 * intensity)}Hz",
                "volume": "+0%",
                "style": "calm",
            },
        }

        # Merge with base parameters
        if emotion in emotion_map:
            base_params.update(emotion_map[emotion])

        return base_params

    async def _detect_emotion(self, text: str) -> Emotion:
        """Detect emotion from text"""
        # Check cache first
        cache_key = text[:100]  # Use first 100 chars as cache key
        if cache_key in self.emotion_cache:
            return self.emotion_cache[cache_key]

        # Try LLM-based detection if available
        if self.llm_client:
            try:
                emotion = await self._llm_emotion_detection(text)
                self.emotion_cache[cache_key] = emotion
                return emotion
            except Exception as e:
                logger.warning(f"LLM emotion detection failed: {e}")

        # Fallback to keyword-based detection
        emotion = self._keyword_emotion_detection(text)
        self.emotion_cache[cache_key] = emotion
        return emotion

    async def _llm_emotion_detection(self, text: str) -> Emotion:
        """Detect emotion using LLM"""
        prompt = f"""Detect the primary emotion in this text.

Text: {text}

Choose ONE from: HAPPY, SAD, ANGRY, SURPRISED, GENTLE, EXCITED, CALM, NEUTRAL

Return only the emotion name:"""

        response = await self.llm_client.chat(
            [
                {"role": "system", "content": "You are an emotion analysis expert."},
                {"role": "user", "content": prompt},
            ]
        )

        emotion_text = response.get("content", "NEUTRAL").strip().upper()

        # Map to enum
        for emotion in Emotion:
            if emotion.name in emotion_text:
                return emotion

        return Emotion.NEUTRAL

    def _keyword_emotion_detection(self, text: str) -> Emotion:
        """Detect emotion using keywords"""
        text_lower = text.lower()

        # Emotion keywords
        emotion_keywords = {
            Emotion.HAPPY: ["开心", "高兴", "快乐", "喜欢", "哈哈", "笑", "happy", "joy"],
            Emotion.SAD: ["难过", "伤心", "悲伤", "失望", "遗憾", "sad", "sorry"],
            Emotion.ANGRY: ["生气", "愤怒", "讨厌", "烦", "气", "angry", "mad"],
            Emotion.SURPRISED: ["惊讶", "震惊", "没想到", "竟然", "surprised", "wow"],
            Emotion.EXCITED: ["激动", "兴奋", "期待", "太棒了", "excited", "great"],
            Emotion.GENTLE: ["温柔", "温暖", "柔和", "轻声", "gentle", "soft"],
            Emotion.CALM: ["平静", "冷静", "淡定", "稳重", "calm", "peace"],
        }

        # Count keyword matches
        emotion_scores = {}
        for emotion, keywords in emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                emotion_scores[emotion] = score

        # Return emotion with highest score
        if emotion_scores:
            return max(emotion_scores, key=emotion_scores.get)

        return Emotion.NEUTRAL

    def _split_by_emotion_context(self, text: str) -> list:
        """Split text by emotion context"""
        # Split by sentences
        sentences = re.split(r"([。！？.!?]+)", text)

        # Combine sentences with their punctuation
        combined = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                combined.append(sentences[i] + sentences[i + 1])
            else:
                combined.append(sentences[i])

        # Detect emotion for each sentence
        segments = []
        for sentence in combined:
            if sentence.strip():
                emotion = self._keyword_emotion_detection(sentence)
                segments.append((sentence, emotion))

        return segments

    def _escape_ssml(self, text: str) -> str:
        """Escape special characters for SSML"""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")
        return text

    async def synthesize_with_emphasis(
        self, text: str, emphasis_words: list, emotion: Emotion | None = None
    ) -> bytes:
        """Synthesize with word emphasis"""
        # Build SSML with emphasis tags
        for word in emphasis_words:
            text = text.replace(word, f'<emphasis level="strong">{word}</emphasis>')

        # Synthesize with emotion
        return await self.synthesize_with_emotion(text, emotion)

    def get_available_emotions(self) -> list:
        """Get list of available emotions"""
        return [emotion.value for emotion in Emotion]

    def get_emotion_statistics(self) -> dict:
        """Get emotion usage statistics"""
        emotion_counts = {}
        for emotion in self.emotion_cache.values():
            emotion_name = emotion.value
            emotion_counts[emotion_name] = emotion_counts.get(emotion_name, 0) + 1

        return {"cache_size": len(self.emotion_cache), "emotion_distribution": emotion_counts}
