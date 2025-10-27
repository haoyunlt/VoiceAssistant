# Voice Engine 服务功能清单与迭代计划

## 服务概述

Voice Engine 是语音引擎服务，提供 ASR（自动语音识别）、TTS（文本转语音）、VAD（语音活动检测）功能。

**技术栈**: FastAPI + Whisper + Edge TTS + Silero VAD + Python 3.11+

**端口**: 8004

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. ASR (语音识别)
- ✅ 基于 Faster-Whisper 的批量识别
- ✅ 文件上传识别
- ✅ 多语言支持（中文、英文）
- ✅ VAD 集成（语音活动检测）
- ✅ 置信度评分
- ✅ 时间戳和分段输出

#### 2. TTS (文本转语音)
- ✅ 基于 Edge TTS 的语音合成
- ✅ 批量合成
- ✅ 流式合成
- ✅ 多音色支持
- ✅ 音色列表查询
- ✅ 速度和音调调节
- ✅ TTS 结果缓存

#### 3. VAD (语音活动检测)
- ✅ 基于 Silero VAD 的检测
- ✅ 批量检测
- ✅ 文件上传检测
- ✅ 可配置阈值
- ✅ 语音段时间戳

#### 4. API 接口
- ✅ `/api/v1/asr/recognize` - ASR 批量识别
- ✅ `/api/v1/asr/recognize/upload` - ASR 文件上传
- ✅ `/api/v1/tts/synthesize` - TTS 批量合成
- ✅ `/api/v1/tts/synthesize/stream` - TTS 流式合成
- ✅ `/api/v1/tts/voices` - 音色列表
- ✅ `/api/v1/vad/detect` - VAD 检测
- ✅ `/api/v1/vad/detect/upload` - VAD 文件上传
- ✅ `/health` - 健康检查

#### 5. 基础设施
- ✅ FastAPI 应用框架
- ✅ Pydantic 数据模型
- ✅ 日志配置
- ✅ 配置管理
- ✅ Docker 支持

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代1：2周）

#### 1. ASR 流式识别
**当前状态**: 未实现

**位置**: `algo/voice-engine/app/routers/asr.py`

**待实现**:

```python
# 文件: algo/voice-engine/app/routers/asr.py
# 当前TODO: 第98行 - 实现流式识别

@router.websocket("/api/v1/asr/recognize/stream")
async def recognize_stream(websocket: WebSocket):
    """
    WebSocket 流式语音识别
    客户端持续发送音频数据，服务端实时返回识别结果
    """
    await websocket.accept()
    
    try:
        # 初始化流式识别器
        streaming_asr = StreamingASR(
            model=app.state.whisper_model,
            vad_model=app.state.vad_model
        )
        
        # 音频缓冲区
        audio_buffer = bytearray()
        
        while True:
            # 接收音频数据
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            # 解析消息
            data = json.loads(message["text"]) if "text" in message else message
            
            if data.get("type") == "audio":
                # 添加到缓冲区
                audio_chunk = base64.b64decode(data["audio"])
                audio_buffer.extend(audio_chunk)
                
                # 检查是否有足够数据进行识别
                if len(audio_buffer) >= streaming_asr.min_chunk_size:
                    # 执行 VAD
                    speech_segments = streaming_asr.detect_speech(
                        bytes(audio_buffer)
                    )
                    
                    # 对语音段进行识别
                    for segment in speech_segments:
                        result = await streaming_asr.recognize_segment(segment)
                        
                        # 发送部分结果
                        await websocket.send_json({
                            "type": "partial",
                            "text": result["text"],
                            "confidence": result["confidence"],
                            "is_final": False
                        })
                    
                    # 清空已处理的部分
                    audio_buffer = bytearray()
            
            elif data.get("type") == "end":
                # 处理剩余缓冲区
                if len(audio_buffer) > 0:
                    final_result = await streaming_asr.recognize_segment(
                        bytes(audio_buffer)
                    )
                    
                    await websocket.send_json({
                        "type": "final",
                        "text": final_result["text"],
                        "confidence": final_result["confidence"],
                        "is_final": True
                    })
                
                break
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Streaming ASR error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()


class StreamingASR:
    """流式 ASR 识别器"""
    
    def __init__(self, model, vad_model):
        self.model = model
        self.vad_model = vad_model
        self.min_chunk_size = 16000 * 2  # 2秒音频 (16kHz)
        self.sample_rate = 16000
    
    def detect_speech(self, audio_bytes: bytes) -> List[AudioSegment]:
        """使用 VAD 检测语音段"""
        # 转换为 numpy 数组
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # VAD 检测
        speech_timestamps = self.vad_model(
            audio_np,
            self.sample_rate
        )
        
        # 提取语音段
        segments = []
        for ts in speech_timestamps:
            start_sample = int(ts['start'] * self.sample_rate)
            end_sample = int(ts['end'] * self.sample_rate)
            segment_audio = audio_np[start_sample:end_sample]
            
            segments.append(AudioSegment(
                audio=segment_audio,
                start_time=ts['start'],
                end_time=ts['end']
            ))
        
        return segments
    
    async def recognize_segment(self, segment: AudioSegment) -> dict:
        """识别单个语音段"""
        # 使用 Whisper 识别
        segments, info = self.model.transcribe(
            segment.audio,
            language="zh",
            beam_size=5
        )
        
        # 提取结果
        text = ""
        for seg in segments:
            text += seg.text
        
        return {
            "text": text.strip(),
            "confidence": getattr(info, 'avg_logprob', 0.0),
            "language": info.language
        }
```

**验收标准**:
- [ ] 支持 WebSocket 连接
- [ ] 实时接收音频流
- [ ] 增量返回识别结果
- [ ] VAD 实时检测
- [ ] 延迟 < 500ms

#### 2. Azure Speech SDK 集成
**当前状态**: 未实现

**位置**: `algo/voice-engine/app/services/asr_service.py`, `tts_service.py`, `azure_speech_service.py`

**待实现**:

```python
# 文件: algo/voice-engine/app/services/azure_speech_service.py

import azure.cognitiveservices.speech as speechsdk
from typing import Optional

class AzureSpeechService:
    """Azure Speech SDK 服务"""
    
    def __init__(self):
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech credentials not configured")
        
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
    
    async def recognize_from_audio(
        self,
        audio_data: bytes,
        language: str = "zh-CN"
    ) -> dict:
        """
        使用 Azure Speech SDK 进行 ASR
        """
        # 配置识别器
        self.speech_config.speech_recognition_language = language
        
        # 创建音频流
        audio_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
        
        # 创建识别器
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )
        
        # 写入音频数据
        audio_stream.write(audio_data)
        audio_stream.close()
        
        # 执行识别
        result = speech_recognizer.recognize_once()
        
        # 处理结果
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return {
                "text": result.text,
                "confidence": result.confidence,
                "language": language
            }
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {
                "text": "",
                "confidence": 0.0,
                "error": "No speech recognized"
            }
        else:
            return {
                "text": "",
                "confidence": 0.0,
                "error": f"Recognition failed: {result.reason}"
            }
    
    async def synthesize_to_audio(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> bytes:
        """
        使用 Azure Speech SDK 进行 TTS
        """
        # 配置语音
        self.speech_config.speech_synthesis_voice_name = voice
        
        # 构建 SSML
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
            <voice name='{voice}'>
                <prosody rate='{rate}' pitch='{pitch}'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        
        # 创建合成器（输出到内存）
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=None  # 使用内存流
        )
        
        # 执行合成
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        else:
            raise Exception(f"TTS failed: {result.reason}")
    
    async def continuous_recognition(
        self,
        websocket: WebSocket,
        language: str = "zh-CN"
    ):
        """
        连续识别（用于 WebSocket 流式）
        """
        self.speech_config.speech_recognition_language = language
        
        # 创建推送流
        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        
        # 创建识别器
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )
        
        # 设置事件处理器
        def recognizing_cb(evt):
            """部分结果"""
            asyncio.create_task(
                websocket.send_json({
                    "type": "partial",
                    "text": evt.result.text,
                    "confidence": 0.0
                })
            )
        
        def recognized_cb(evt):
            """最终结果"""
            asyncio.create_task(
                websocket.send_json({
                    "type": "final",
                    "text": evt.result.text,
                    "confidence": evt.result.confidence
                })
            )
        
        # 连接事件
        speech_recognizer.recognizing.connect(recognizing_cb)
        speech_recognizer.recognized.connect(recognized_cb)
        
        # 开始连续识别
        speech_recognizer.start_continuous_recognition()
        
        try:
            while True:
                # 接收音频数据
                message = await websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    break
                
                data = json.loads(message["text"])
                
                if data.get("type") == "audio":
                    audio_chunk = base64.b64decode(data["audio"])
                    push_stream.write(audio_chunk)
                
                elif data.get("type") == "end":
                    break
        
        finally:
            # 停止识别
            speech_recognizer.stop_continuous_recognition()
            push_stream.close()
```

**验收标准**:
- [ ] Azure ASR 集成完成
- [ ] Azure TTS 集成完成
- [ ] 支持连续识别
- [ ] 配置切换（Whisper/Azure）

#### 3. 全双工语音交互
**当前状态**: 部分实现，需完善

**位置**: `algo/voice-engine/app/core/full_duplex_engine.py`

**待实现**:

```python
# 文件: algo/voice-engine/app/core/full_duplex_engine.py
# 当前TODO: 第205行 - 实际实现中需要停止音频播放

class FullDuplexEngine:
    """
    全双工语音交互引擎
    支持同时录音和播放，实现打断功能
    """
    
    def __init__(self):
        self.asr_service = ASRService()
        self.tts_service = TTSService()
        self.vad_service = VADService()
        
        self.is_playing = False
        self.audio_player = None
    
    async def start_session(self, websocket: WebSocket):
        """启动全双工会话"""
        await websocket.accept()
        
        # 创建任务
        asr_task = asyncio.create_task(self._asr_loop(websocket))
        tts_task = asyncio.create_task(self._tts_loop(websocket))
        vad_task = asyncio.create_task(self._vad_loop(websocket))
        
        try:
            # 并发运行
            await asyncio.gather(asr_task, tts_task, vad_task)
        except Exception as e:
            logger.error(f"Full duplex error: {e}")
        finally:
            await self._cleanup()
    
    async def _asr_loop(self, websocket: WebSocket):
        """ASR 循环"""
        audio_buffer = bytearray()
        
        while True:
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            data = json.loads(message["text"])
            
            if data.get("type") == "audio":
                # 添加到缓冲区
                audio_chunk = base64.b64decode(data["audio"])
                audio_buffer.extend(audio_chunk)
                
                # 检查是否有完整语音
                if len(audio_buffer) >= 16000 * 2:  # 2秒
                    # VAD 检测
                    has_speech = await self.vad_service.detect(
                        bytes(audio_buffer)
                    )
                    
                    if has_speech:
                        # 如果正在播放，停止播放（打断）
                        if self.is_playing:
                            await self._stop_playback()
                        
                        # ASR 识别
                        result = await self.asr_service.recognize(
                            bytes(audio_buffer)
                        )
                        
                        # 发送识别结果
                        await websocket.send_json({
                            "type": "asr_result",
                            "text": result["text"],
                            "confidence": result["confidence"]
                        })
                        
                        # 清空缓冲区
                        audio_buffer = bytearray()
    
    async def _tts_loop(self, websocket: WebSocket):
        """TTS 循环"""
        while True:
            # 等待 TTS 请求
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            data = json.loads(message["text"])
            
            if data.get("type") == "tts_request":
                # 合成语音
                audio = await self.tts_service.synthesize(
                    text=data["text"],
                    voice=data.get("voice", "zh-CN-XiaoxiaoNeural")
                )
                
                # 流式播放
                await self._stream_audio(websocket, audio)
    
    async def _stream_audio(self, websocket: WebSocket, audio: bytes):
        """流式播放音频"""
        self.is_playing = True
        
        # 分块发送
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            
            await websocket.send_json({
                "type": "audio_chunk",
                "audio": base64.b64encode(chunk).decode(),
                "is_last": i + chunk_size >= len(audio)
            })
            
            # 小延迟，避免过快
            await asyncio.sleep(0.01)
        
        self.is_playing = False
    
    async def _stop_playback(self):
        """停止音频播放"""
        self.is_playing = False
        logger.info("Playback interrupted by user speech")
    
    async def _vad_loop(self, websocket: WebSocket):
        """VAD 监控循环"""
        # 监控语音活动，用于打断检测
        pass
    
    async def _cleanup(self):
        """清理资源"""
        self.is_playing = False
```

**验收标准**:
- [ ] 支持同时录音和播放
- [ ] 用户说话时自动停止播放
- [ ] 低延迟（< 300ms）
- [ ] 稳定的 WebSocket 连接

#### 4. 语音克隆功能
**当前状态**: 未实现

**位置**: `algo/voice-engine/app/services/voice_cloning_service.py`

**待实现**:

```python
# 文件: algo/voice-engine/app/services/voice_cloning_service.py
# 当前TODO: 第254行 - 实际的模型训练流程，第311行 - 使用训练好的模型合成

import torch
from TTS.api import TTS

class VoiceCloningService:
    """语音克隆服务"""
    
    def __init__(self):
        # 加载预训练模型
        self.model_name = "tts_models/multilingual/multi-dataset/your_tts"
        self.tts = TTS(model_name=self.model_name, gpu=False)
        
        self.cloned_voices = {}
    
    async def clone_voice(
        self,
        voice_id: str,
        audio_samples: List[bytes],
        text_samples: List[str]
    ) -> dict:
        """
        克隆声音
        
        Args:
            voice_id: 声音ID
            audio_samples: 音频样本列表（至少3个）
            text_samples: 对应的文本列表
            
        Returns:
            克隆结果
        """
        if len(audio_samples) < 3:
            raise ValueError("至少需要3个音频样本")
        
        if len(audio_samples) != len(text_samples):
            raise ValueError("音频和文本数量必须相同")
        
        # 1. 保存音频样本
        sample_paths = []
        for i, audio_data in enumerate(audio_samples):
            path = f"/tmp/voice_clone_{voice_id}_{i}.wav"
            with open(path, 'wb') as f:
                f.write(audio_data)
            sample_paths.append(path)
        
        # 2. 提取说话人嵌入（speaker embedding）
        try:
            # 使用 YourTTS 提取 speaker embedding
            speaker_embedding = self._extract_speaker_embedding(
                sample_paths[0]  # 使用第一个样本
            )
            
            # 3. 存储声音配置
            self.cloned_voices[voice_id] = {
                "speaker_embedding": speaker_embedding,
                "sample_paths": sample_paths,
                "created_at": datetime.utcnow()
            }
            
            return {
                "voice_id": voice_id,
                "status": "success",
                "sample_count": len(audio_samples)
            }
        
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise
    
    def _extract_speaker_embedding(self, audio_path: str) -> torch.Tensor:
        """提取说话人嵌入"""
        # 使用 TTS 模型提取
        embedding = self.tts.synthesizer.tts_model.speaker_manager.encoder.compute_embedding(
            audio_path
        )
        return embedding
    
    async def synthesize_with_cloned_voice(
        self,
        voice_id: str,
        text: str,
        language: str = "zh-cn"
    ) -> bytes:
        """
        使用克隆的声音合成语音
        
        Args:
            voice_id: 声音ID
            text: 要合成的文本
            language: 语言
            
        Returns:
            音频数据
        """
        if voice_id not in self.cloned_voices:
            raise ValueError(f"Voice {voice_id} not found")
        
        voice_data = self.cloned_voices[voice_id]
        speaker_embedding = voice_data["speaker_embedding"]
        
        # 使用克隆的声音合成
        output_path = f"/tmp/synthesized_{voice_id}_{int(time.time())}.wav"
        
        self.tts.tts_to_file(
            text=text,
            speaker_wav=voice_data["sample_paths"][0],  # 参考音频
            language=language,
            file_path=output_path
        )
        
        # 读取合成的音频
        with open(output_path, 'rb') as f:
            audio_data = f.read()
        
        # 清理临时文件
        os.remove(output_path)
        
        return audio_data
    
    async def list_cloned_voices(self) -> List[dict]:
        """列出所有克隆的声音"""
        return [
            {
                "voice_id": voice_id,
                "sample_count": len(data["sample_paths"]),
                "created_at": data["created_at"].isoformat()
            }
            for voice_id, data in self.cloned_voices.items()
        ]
    
    async def delete_cloned_voice(self, voice_id: str):
        """删除克隆的声音"""
        if voice_id in self.cloned_voices:
            # 删除音频文件
            for path in self.cloned_voices[voice_id]["sample_paths"]:
                if os.path.exists(path):
                    os.remove(path)
            
            del self.cloned_voices[voice_id]
```

**API 端点**:
```python
# 文件: algo/voice-engine/app/routers/voice_cloning.py

@router.post("/api/v1/voice/clone")
async def clone_voice(
    voice_id: str = Form(...),
    audio_files: List[UploadFile] = File(...),
    texts: List[str] = Form(...)
):
    """克隆声音"""
    # 读取音频文件
    audio_samples = []
    for file in audio_files:
        audio_data = await file.read()
        audio_samples.append(audio_data)
    
    # 克隆
    result = await voice_cloning_service.clone_voice(
        voice_id=voice_id,
        audio_samples=audio_samples,
        text_samples=texts
    )
    
    return result

@router.post("/api/v1/voice/synthesize/cloned")
async def synthesize_with_cloned_voice(request: ClonedVoiceSynthesizeRequest):
    """使用克隆的声音合成"""
    audio = await voice_cloning_service.synthesize_with_cloned_voice(
        voice_id=request.voice_id,
        text=request.text,
        language=request.language
    )
    
    return Response(
        content=audio,
        media_type="audio/wav"
    )

@router.get("/api/v1/voice/cloned/list")
async def list_cloned_voices():
    """列出克隆的声音"""
    voices = await voice_cloning_service.list_cloned_voices()
    return {"voices": voices}
```

**验收标准**:
- [ ] 支持声音克隆
- [ ] 至少3个样本即可克隆
- [ ] 合成质量高
- [ ] 提供完整 API

#### 5. 音频处理增强
**当前状态**: 未实现

**位置**: `algo/voice-engine/main.py`

**待实现**:

```python
# 文件: algo/voice-engine/app/services/audio_processing_service.py

import noisereduce as nr
import librosa
import soundfile as sf

class AudioProcessingService:
    """音频处理服务"""
    
    def __init__(self):
        self.sample_rate = 16000
    
    async def denoise(
        self,
        audio_data: bytes,
        noise_profile: Optional[bytes] = None
    ) -> bytes:
        """
        降噪处理
        
        Args:
            audio_data: 原始音频数据
            noise_profile: 噪音样本（可选）
            
        Returns:
            降噪后的音频数据
        """
        # 转换为 numpy 数组
        audio_np, sr = self._bytes_to_numpy(audio_data)
        
        # 执行降噪
        if noise_profile:
            noise_np, _ = self._bytes_to_numpy(noise_profile)
            reduced_noise = nr.reduce_noise(
                y=audio_np,
                sr=sr,
                y_noise=noise_np,
                prop_decrease=1.0
            )
        else:
            # 无监督降噪
            reduced_noise = nr.reduce_noise(
                y=audio_np,
                sr=sr,
                stationary=True
            )
        
        # 转换回 bytes
        return self._numpy_to_bytes(reduced_noise, sr)
    
    async def enhance(
        self,
        audio_data: bytes,
        enhancements: List[str]
    ) -> bytes:
        """
        音频增强
        
        Args:
            audio_data: 原始音频
            enhancements: 增强列表 ['normalize', 'equalize', 'compress']
            
        Returns:
            增强后的音频
        """
        audio_np, sr = self._bytes_to_numpy(audio_data)
        
        for enhancement in enhancements:
            if enhancement == 'normalize':
                # 归一化
                audio_np = librosa.util.normalize(audio_np)
            
            elif enhancement == 'equalize':
                # 均衡化
                audio_np = self._equalize(audio_np, sr)
            
            elif enhancement == 'compress':
                # 动态范围压缩
                audio_np = self._compress(audio_np)
        
        return self._numpy_to_bytes(audio_np, sr)
    
    async def change_speed(
        self,
        audio_data: bytes,
        rate: float
    ) -> bytes:
        """
        改变语速（不改变音调）
        
        Args:
            audio_data: 原始音频
            rate: 速率 (1.0 = 原速, 1.5 = 1.5倍速)
            
        Returns:
            调整后的音频
        """
        audio_np, sr = self._bytes_to_numpy(audio_data)
        
        # 时间拉伸
        stretched = librosa.effects.time_stretch(audio_np, rate=rate)
        
        return self._numpy_to_bytes(stretched, sr)
    
    async def change_pitch(
        self,
        audio_data: bytes,
        semitones: int
    ) -> bytes:
        """
        改变音调（不改变语速）
        
        Args:
            audio_data: 原始音频
            semitones: 半音数 (12 = 升高1个八度, -12 = 降低1个八度)
            
        Returns:
            调整后的音频
        """
        audio_np, sr = self._bytes_to_numpy(audio_data)
        
        # 音调变换
        shifted = librosa.effects.pitch_shift(
            audio_np,
            sr=sr,
            n_steps=semitones
        )
        
        return self._numpy_to_bytes(shifted, sr)
    
    async def mix_audio(
        self,
        audio_list: List[bytes],
        volumes: List[float]
    ) -> bytes:
        """
        混音
        
        Args:
            audio_list: 音频列表
            volumes: 对应的音量 (0.0-1.0)
            
        Returns:
            混音后的音频
        """
        if len(audio_list) != len(volumes):
            raise ValueError("Audio count must match volume count")
        
        # 转换所有音频
        audio_arrays = []
        max_length = 0
        
        for audio_data in audio_list:
            audio_np, sr = self._bytes_to_numpy(audio_data)
            audio_arrays.append(audio_np)
            max_length = max(max_length, len(audio_np))
        
        # 填充到相同长度并混音
        mixed = np.zeros(max_length)
        
        for audio_np, volume in zip(audio_arrays, volumes):
            # 填充
            padded = np.pad(audio_np, (0, max_length - len(audio_np)))
            # 混音
            mixed += padded * volume
        
        # 归一化
        mixed = librosa.util.normalize(mixed)
        
        return self._numpy_to_bytes(mixed, sr)
    
    def _bytes_to_numpy(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """bytes 转 numpy"""
        # 使用 librosa 加载
        audio_np, sr = librosa.load(
            io.BytesIO(audio_data),
            sr=self.sample_rate
        )
        return audio_np, sr
    
    def _numpy_to_bytes(self, audio_np: np.ndarray, sr: int) -> bytes:
        """numpy 转 bytes"""
        buffer = io.BytesIO()
        sf.write(buffer, audio_np, sr, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    def _equalize(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """均衡化"""
        # 简单的频段增强
        return audio
    
    def _compress(self, audio: np.ndarray) -> np.ndarray:
        """动态范围压缩"""
        threshold = 0.5
        ratio = 4.0
        
        compressed = np.copy(audio)
        mask = np.abs(compressed) > threshold
        compressed[mask] = threshold + (compressed[mask] - threshold) / ratio
        
        return compressed
```

**API 端点**:
```python
@router.post("/api/v1/audio/denoise")
async def denoise_audio(file: UploadFile = File(...)):
    """降噪"""
    audio_data = await file.read()
    processed = await audio_processing_service.denoise(audio_data)
    return Response(content=processed, media_type="audio/wav")

@router.post("/api/v1/audio/enhance")
async def enhance_audio(
    file: UploadFile = File(...),
    enhancements: List[str] = Query(...)
):
    """增强"""
    audio_data = await file.read()
    processed = await audio_processing_service.enhance(audio_data, enhancements)
    return Response(content=processed, media_type="audio/wav")
```

**验收标准**:
- [ ] 降噪功能完善
- [ ] 音频增强效果好
- [ ] 支持语速、音调调整
- [ ] 支持混音

---

### 🔄 P1 - 高级功能（迭代2：1周）

#### 1. 多语言支持增强
- [ ] 支持自动语言检测
- [ ] 支持多语言混合识别
- [ ] 增加更多语言支持

#### 2. 实时性能优化
- [ ] 模型量化（INT8）
- [ ] 批处理优化
- [ ] GPU 加速支持
- [ ] 缓存优化

#### 3. 高级 VAD
- [ ] 端点检测优化
- [ ] 噪音鲁棒性增强
- [ ] 自适应阈值

---

### 🔄 P2 - 优化增强（迭代3：1周）

#### 1. 质量优化
- [ ] ASR 后处理（标点、纠错）
- [ ] TTS 韵律优化
- [ ] 情感识别和合成

#### 2. 可观测性
- [ ] Prometheus 指标
- [ ] 性能监控
- [ ] 质量监控

#### 3. 成本优化
- [ ] 模型缓存
- [ ] 智能降级
- [ ] 批处理优化

---

## 三、详细实施方案

### 阶段1：核心功能（Week 1-2）

#### Day 1-4: 流式识别和 Azure 集成
1. 实现 WebSocket 流式 ASR
2. 集成 Azure Speech SDK
3. 测试和优化

#### Day 5-7: 全双工和语音克隆
1. 完善全双工引擎
2. 实现语音克隆功能
3. 测试

#### Day 8-10: 音频处理
1. 实现降噪和增强
2. 实现语速、音调调整
3. 测试

#### Day 11-14: 集成和优化
1. 端到端测试
2. 性能优化
3. 文档更新

### 阶段2：高级功能（Week 3）

#### Day 15-17: 多语言和性能
1. 多语言支持增强
2. 性能优化
3. 测试

#### Day 18-21: 质量和监控
1. 质量优化
2. 监控指标
3. 文档

---

## 四、验收标准

### 功能验收
- [ ] 流式识别延迟 < 500ms
- [ ] Azure 集成完成
- [ ] 全双工正常工作
- [ ] 语音克隆质量高
- [ ] 音频处理效果好

### 性能验收
- [ ] ASR 实时率 > 1.0
- [ ] TTS 首字节时间 < 200ms
- [ ] 支持 50 并发
- [ ] 内存使用 < 2GB

### 质量验收
- [ ] ASR 准确率 > 95%
- [ ] TTS 自然度评分 > 4.0/5.0
- [ ] 所有 TODO 清理
- [ ] 文档完整

---

## 总结

Voice Engine 的主要待完成功能：

1. **流式识别**: WebSocket 实时 ASR
2. **Azure 集成**: 企业级语音服务
3. **全双工**: 同时录音和播放，支持打断
4. **语音克隆**: 个性化语音合成
5. **音频处理**: 降噪、增强、变速变调

完成后将具备生产级语音服务能力。


