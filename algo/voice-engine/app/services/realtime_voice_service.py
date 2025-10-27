"""
Realtime Full-Duplex Voice Conversation Service
"""

from typing import AsyncIterator, Optional, Dict, Any
from collections import deque
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RealtimeVoiceService:
    """Real-time full-duplex voice conversation service"""
    
    def __init__(
        self,
        asr_service,
        tts_service,
        vad_service,
        llm_client,
        buffer_size_ms: int = 200,
        vad_threshold: float = 0.5
    ):
        self.asr_service = asr_service
        self.tts_service = tts_service
        self.vad_service = vad_service
        self.llm_client = llm_client
        self.buffer_size_ms = buffer_size_ms
        self.vad_threshold = vad_threshold
        
        # Audio buffers
        self.input_buffer = deque(maxlen=100)
        self.output_buffer = deque(maxlen=100)
        
        # State management
        self.is_speaking = False
        self.is_listening = True
        self.is_processing = False
        self.conversation_active = False
        
        # Statistics
        self.stats = {
            "total_turns": 0,
            "total_interruptions": 0,
            "avg_response_latency": 0.0,
            "total_response_time": 0.0
        }
        
    async def start_duplex_conversation(
        self,
        session_id: str,
        input_stream: AsyncIterator[bytes],
        output_callback
    ):
        """Start full-duplex conversation"""
        self.conversation_active = True
        logger.info(f"Starting duplex conversation: {session_id}")
        
        try:
            # Run input, output, and interruption handling in parallel
            await asyncio.gather(
                self._process_input_stream(input_stream, session_id),
                self._process_output_stream(output_callback, session_id),
                self._handle_interruptions(session_id),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Duplex conversation error: {e}")
        finally:
            self.conversation_active = False
            logger.info(f"Duplex conversation ended: {session_id}")
            
    async def stop_conversation(self):
        """Stop conversation"""
        self.conversation_active = False
        self.input_buffer.clear()
        self.output_buffer.clear()
        
    async def _process_input_stream(
        self,
        stream: AsyncIterator[bytes],
        session_id: str
    ):
        """Process input audio stream"""
        accumulated_audio = b''
        silence_duration = 0
        speech_detected = False
        
        try:
            async for audio_chunk in stream:
                if not self.conversation_active:
                    break
                    
                # VAD detection
                vad_result = await self.vad_service.detect(audio_chunk)
                is_speech = vad_result.get("is_speech", False)
                confidence = vad_result.get("confidence", 0.0)
                
                if is_speech and confidence >= self.vad_threshold:
                    # Speech detected
                    speech_detected = True
                    silence_duration = 0
                    accumulated_audio += audio_chunk
                    self.input_buffer.append(audio_chunk)
                    
                    # If we were speaking, this is an interruption
                    if self.is_speaking:
                        self.stats["total_interruptions"] += 1
                        logger.info(f"User interruption detected")
                        await self._handle_user_interruption()
                        
                elif speech_detected:
                    # Potential end of speech
                    silence_duration += len(audio_chunk) / 16000  # Assuming 16kHz
                    
                    if silence_duration >= 0.5:  # 500ms silence
                        # End of utterance
                        if len(accumulated_audio) > 0:
                            logger.info(f"End of utterance detected, processing...")
                            await self._process_utterance(
                                accumulated_audio,
                                session_id
                            )
                            accumulated_audio = b''
                            speech_detected = False
                            silence_duration = 0
                            
        except Exception as e:
            logger.error(f"Input stream processing error: {e}")
            
    async def _process_utterance(self, audio_data: bytes, session_id: str):
        """Process complete utterance"""
        try:
            start_time = time.time()
            self.is_processing = True
            
            # 1. ASR - transcribe audio
            logger.debug("Starting ASR...")
            asr_start = time.time()
            asr_result = await self.asr_service.recognize_from_bytes(
                audio_data,
                language="auto"
            )
            asr_latency = time.time() - asr_start
            
            text = asr_result.get("text", "").strip()
            if not text:
                logger.warning("Empty transcription")
                self.is_processing = False
                return
                
            logger.info(f"ASR result ({asr_latency:.3f}s): {text}")
            
            # 2. LLM - generate response
            logger.debug("Generating LLM response...")
            llm_start = time.time()
            llm_response = await self.llm_client.chat([
                {"role": "user", "content": text}
            ])
            llm_latency = time.time() - llm_start
            
            response_text = llm_response.get("content", "")
            logger.info(f"LLM response ({llm_latency:.3f}s): {response_text[:50]}...")
            
            # 3. TTS - synthesize speech (streaming)
            logger.debug("Starting TTS synthesis...")
            tts_start = time.time()
            first_chunk_received = False
            
            async for audio_chunk in self.tts_service.synthesize_streaming(
                response_text,
                voice_name="zh-CN-XiaoxiaoNeural"
            ):
                if not first_chunk_received:
                    ttfb = time.time() - tts_start
                    logger.info(f"TTS TTFB: {ttfb:.3f}s")
                    first_chunk_received = True
                    
                # Add to output buffer
                self.output_buffer.append(audio_chunk)
                self.is_speaking = True
                
            # Update statistics
            total_latency = time.time() - start_time
            self.stats["total_turns"] += 1
            self.stats["total_response_time"] += total_latency
            self.stats["avg_response_latency"] = (
                self.stats["total_response_time"] / self.stats["total_turns"]
            )
            
            logger.info(f"Turn complete - Total latency: {total_latency:.3f}s")
            self.is_processing = False
            
        except Exception as e:
            logger.error(f"Utterance processing error: {e}")
            self.is_processing = False
            
    async def _process_output_stream(self, output_callback, session_id: str):
        """Process output audio stream"""
        try:
            while self.conversation_active:
                if self.output_buffer:
                    # Get audio chunk from buffer
                    audio_chunk = self.output_buffer.popleft()
                    
                    # Send to output
                    try:
                        await output_callback(audio_chunk)
                    except Exception as e:
                        logger.error(f"Output callback error: {e}")
                        
                    # Small delay to control output rate
                    await asyncio.sleep(0.01)
                else:
                    # No audio to play
                    self.is_speaking = False
                    await asyncio.sleep(0.05)
                    
        except Exception as e:
            logger.error(f"Output stream processing error: {e}")
            
    async def _handle_interruptions(self, session_id: str):
        """Handle user interruptions"""
        try:
            while self.conversation_active:
                # Check for interruption condition
                if self.is_listening and self.is_speaking and len(self.input_buffer) > 0:
                    # User is speaking while we're playing audio
                    logger.info("Interruption detected, clearing output buffer")
                    await self._handle_user_interruption()
                    
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logger.error(f"Interruption handling error: {e}")
            
    async def _handle_user_interruption(self):
        """Handle user interrupting the assistant"""
        # Clear output buffer immediately
        self.output_buffer.clear()
        self.is_speaking = False
        logger.info("Output cleared due to interruption")
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        return {
            **self.stats,
            "buffer_sizes": {
                "input": len(self.input_buffer),
                "output": len(self.output_buffer)
            },
            "state": {
                "is_speaking": self.is_speaking,
                "is_listening": self.is_listening,
                "is_processing": self.is_processing,
                "active": self.conversation_active
            }
        }


class StreamingOptimizer:
    """Optimizer for streaming audio processing"""
    
    def __init__(self):
        self.chunk_size = 1024  # bytes
        self.sample_rate = 16000
        self.latency_targets = {
            "asr": 0.5,    # 500ms
            "llm": 1.0,    # 1s
            "tts_ttfb": 0.3,  # 300ms
            "total": 2.0   # 2s
        }
        
    async def optimize_asr_streaming(
        self,
        asr_service,
        audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Optimize ASR for streaming"""
        buffer = b''
        min_chunk_duration = 0.5  # seconds
        min_chunk_size = int(self.sample_rate * 2 * min_chunk_duration)  # 16-bit audio
        
        async for chunk in audio_chunks:
            buffer += chunk
            
            if len(buffer) >= min_chunk_size:
                # Process accumulated buffer
                result = await asr_service.recognize_from_bytes(buffer)
                text = result.get("text", "")
                
                if text:
                    yield text
                    
                buffer = b''
                
    async def optimize_tts_streaming(
        self,
        tts_service,
        text: str
    ) -> AsyncIterator[bytes]:
        """Optimize TTS for low TTFB"""
        # Split text into sentences for faster TTFB
        sentences = self._split_into_sentences(text)
        
        for sentence in sentences:
            async for audio_chunk in tts_service.synthesize_streaming(sentence):
                yield audio_chunk
                
    def _split_into_sentences(self, text: str) -> list:
        """Split text into sentences"""
        import re
        sentences = re.split(r'[。！？.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
        
    def calculate_optimal_buffer_size(
        self,
        latency_target_ms: int,
        sample_rate: int = 16000,
        bit_depth: int = 16
    ) -> int:
        """Calculate optimal buffer size for target latency"""
        bytes_per_sample = bit_depth // 8
        samples_needed = int((latency_target_ms / 1000.0) * sample_rate)
        buffer_size = samples_needed * bytes_per_sample
        return buffer_size

