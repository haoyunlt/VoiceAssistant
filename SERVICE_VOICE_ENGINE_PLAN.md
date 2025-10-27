# Voice Engine - 功能清单与迭代计划

> **服务名称**: Voice Engine (algo/voice-engine)
> **当前版本**: v1.0.0
> **完成度**: 70%
> **优先级**: P0 (核心服务)

---

## 📊 执行摘要

Voice Engine 是语音处理的核心服务,提供 ASR(语音识别)、TTS(语音合成)和 VAD(语音活动检测)功能。当前已实现基础功能,但在流式处理、多厂商支持和性能优化方面仍有提升空间。

### 关键指标

| 指标           | 当前状态        | 目标状态 | 差距  |
| -------------- | --------------- | -------- | ----- |
| ASR 识别准确率 | ~85%            | > 95%    | ⚠️ 中 |
| TTS 缓存命中率 | 0% (未实现)     | > 40%    | ⚠️ 高 |
| VAD 检测准确率 | ~85% (Silero)   | > 95%    | ⚠️ 中 |
| 流式 ASR       | 不支持          | 完整支持 | ⚠️ 高 |
| 厂商支持       | 仅 Whisper/Edge | +Azure   | ⚠️ 中 |

---

## 🔍 未完成功能清单

### P0 级别 (阻塞性功能)

#### 1. 流式 ASR 识别

**文件**: `app/routers/asr.py:91`

**问题描述**:

```python
# TODO: 实现流式识别
```

**影响**: 无法实现实时语音对话,用户体验差

**详细设计方案**:

```python
# app/services/streaming_asr_service.py

from typing import AsyncIterator
import asyncio
import numpy as np
from faster_whisper import WhisperModel
import webrtcvad

class StreamingASRService:
    """流式ASR服务"""

    def __init__(
        self,
        model_size: str = "base",
        chunk_duration_ms: int = 300,
        vad_mode: int = 3
    ):
        # Whisper模型
        self.whisper_model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8"
        )

        # VAD (WebRTC)
        self.vad = webrtcvad.Vad(vad_mode)

        # 音频缓冲区
        self.chunk_duration_ms = chunk_duration_ms
        self.sample_rate = 16000
        self.chunk_size = int(self.sample_rate * chunk_duration_ms / 1000)

        # 状态管理
        self.audio_buffer = bytearray()
        self.speech_buffer = bytearray()
        self.is_speaking = False
        self.silence_duration = 0
        self.max_silence_duration_ms = 1500  # 1.5秒静音触发识别

    async def process_stream(
        self,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[dict]:
        """处理音频流"""

        yield {
            "type": "session_start",
            "sample_rate": self.sample_rate,
            "chunk_duration_ms": self.chunk_duration_ms
        }

        async for audio_chunk in audio_stream:
            # 添加到缓冲区
            self.audio_buffer.extend(audio_chunk)

            # 处理完整的chunk
            while len(self.audio_buffer) >= self.chunk_size * 2:  # 16-bit = 2 bytes
                chunk = bytes(self.audio_buffer[:self.chunk_size * 2])
                self.audio_buffer = self.audio_buffer[self.chunk_size * 2:]

                # VAD检测
                is_speech = self.vad.is_speech(chunk, self.sample_rate)

                if is_speech:
                    # 检测到语音
                    if not self.is_speaking:
                        # 语音开始
                        self.is_speaking = True
                        self.speech_buffer = bytearray()

                        yield {
                            "type": "speech_start",
                            "timestamp": self._get_timestamp()
                        }

                    # 累积语音数据
                    self.speech_buffer.extend(chunk)
                    self.silence_duration = 0

                    # 增量识别 (可选)
                    if len(self.speech_buffer) >= self.sample_rate * 2 * 3:  # 每3秒
                        partial_text = await self._recognize_partial(self.speech_buffer)

                        yield {
                            "type": "partial_result",
                            "text": partial_text,
                            "is_final": False
                        }

                else:
                    # 静音
                    if self.is_speaking:
                        self.silence_duration += self.chunk_duration_ms
                        self.speech_buffer.extend(chunk)  # 保留静音以保持连贯性

                        # 静音超过阈值,触发最终识别
                        if self.silence_duration >= self.max_silence_duration_ms:
                            final_text = await self._recognize_final(self.speech_buffer)

                            yield {
                                "type": "final_result",
                                "text": final_text,
                                "is_final": True,
                                "duration_ms": len(self.speech_buffer) / self.sample_rate / 2 * 1000
                            }

                            # 重置状态
                            self.is_speaking = False
                            self.speech_buffer = bytearray()
                            self.silence_duration = 0

                            yield {
                                "type": "speech_end",
                                "timestamp": self._get_timestamp()
                            }

        # 流结束,处理剩余数据
        if self.is_speaking and len(self.speech_buffer) > 0:
            final_text = await self._recognize_final(self.speech_buffer)

            yield {
                "type": "final_result",
                "text": final_text,
                "is_final": True
            }

        yield {
            "type": "session_end"
        }

    async def _recognize_partial(self, audio_data: bytes) -> str:
        """增量识别 (快速,低准确率)"""
        # 使用较小的beam_size加速
        segments, _ = self.whisper_model.transcribe(
            self._bytes_to_audio(audio_data),
            beam_size=1,
            best_of=1,
            temperature=0.0
        )

        text = " ".join([seg.text for seg in segments])
        return text.strip()

    async def _recognize_final(self, audio_data: bytes) -> str:
        """最终识别 (完整准确率)"""
        segments, info = self.whisper_model.transcribe(
            self._bytes_to_audio(audio_data),
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True
        )

        text = " ".join([seg.text for seg in segments])
        return text.strip()

    def _bytes_to_audio(self, audio_bytes: bytes) -> np.ndarray:
        """字节转音频数组"""
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        return audio_array.astype(np.float32) / 32768.0

    def _get_timestamp(self) -> float:
        """获取时间戳"""
        import time
        return time.time()


# WebSocket API 实现

from fastapi import WebSocket, WebSocketDisconnect
import json

@router.websocket("/ws/asr/stream")
async def websocket_asr_stream(websocket: WebSocket):
    """WebSocket 流式ASR"""

    await websocket.accept()

    try:
        # 接收配置
        config_msg = await websocket.receive_json()

        model_size = config_msg.get("model_size", "base")
        language = config_msg.get("language", "zh")

        # 初始化流式ASR服务
        streaming_asr = StreamingASRService(
            model_size=model_size,
            chunk_duration_ms=300
        )

        async def audio_generator():
            """音频生成器"""
            while True:
                try:
                    message = await websocket.receive()

                    if "bytes" in message:
                        yield message["bytes"]
                    elif "text" in message:
                        # 控制命令
                        cmd = json.loads(message["text"])
                        if cmd.get("type") == "end":
                            break

                except WebSocketDisconnect:
                    break

        # 处理流式识别
        async for result in streaming_asr.process_stream(audio_generator()):
            await websocket.send_json(result)

    except WebSocketDisconnect:
        print("Client disconnected")

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })

    finally:
        await websocket.close()
```

**前端集成示例**:

```javascript
// React 流式ASR客户端

class StreamingASRClient {
  constructor(wsUrl, config) {
    this.wsUrl = wsUrl;
    this.config = config;
    this.ws = null;
    this.mediaRecorder = null;
    this.onResult = null;
  }

  async start() {
    // 连接WebSocket
    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      // 发送配置
      this.ws.send(JSON.stringify(this.config));

      // 开始录音
      this.startRecording();
    };

    this.ws.onmessage = (event) => {
      const result = JSON.parse(event.data);

      if (this.onResult) {
        this.onResult(result);
      }
    };
  }

  async startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    // 使用MediaRecorder录音
    this.mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus',
    });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0 && this.ws.readyState === WebSocket.OPEN) {
        // 发送音频数据
        this.ws.send(event.data);
      }
    };

    // 每300ms发送一次数据
    this.mediaRecorder.start(300);
  }

  stop() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
    }

    if (this.ws) {
      this.ws.send(JSON.stringify({ type: 'end' }));
      this.ws.close();
    }
  }
}

// 使用示例
const client = new StreamingASRClient('ws://localhost:8001/ws/asr/stream', {
  model_size: 'base',
  language: 'zh',
});

client.onResult = (result) => {
  if (result.type === 'partial_result') {
    console.log('增量结果:', result.text);
    setPartialText(result.text);
  } else if (result.type === 'final_result') {
    console.log('最终结果:', result.text);
    setFinalText(result.text);
  }
};

client.start();
```

**验收标准**:

- [ ] WebSocket 连接稳定
- [ ] 增量识别延迟 < 500ms
- [ ] 最终识别准确率 > 90%
- [ ] 端点检测准确 (VAD)
- [ ] 并发支持 > 20 连接

**工作量**: 3-4 天

---

#### 2. TTS Redis 缓存

**文件**: `app/services/tts_service.py:194,199`

**问题描述**:

```python
# TODO: 使用 Redis 缓存
```

**影响**: 相同文本重复合成,浪费资源和时间

**详细设计方案**:

```python
# app/infrastructure/tts_cache.py

import redis
import hashlib
import base64
from typing import Optional
from datetime import timedelta

class TTSRedisCache:
    """TTS Redis缓存"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        ttl_days: int = 30,
        max_cache_size_mb: int = 1000
    ):
        self.redis = redis.from_url(redis_url)
        self.ttl = timedelta(days=ttl_days)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # 转为字节

    def _generate_key(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        format: str
    ) -> str:
        """生成缓存键"""
        cache_input = f"{text}:{voice}:{rate}:{pitch}:{format}"
        hash_key = hashlib.sha256(cache_input.encode()).hexdigest()
        return f"tts:cache:{hash_key}"

    def get(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        format: str = "mp3"
    ) -> Optional[bytes]:
        """获取缓存"""
        key = self._generate_key(text, voice, rate, pitch, format)

        cached = self.redis.get(key)

        if cached:
            # 更新访问统计
            self.redis.hincrby(f"{key}:stats", "hits", 1)
            self.redis.expire(key, self.ttl)  # 刷新TTL

            return base64.b64decode(cached)

        return None

    def set(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        format: str,
        audio_data: bytes
    ):
        """设置缓存"""
        key = self._generate_key(text, voice, rate, pitch, format)

        # 检查缓存大小
        current_size = self._get_total_cache_size()
        audio_size = len(audio_data)

        if current_size + audio_size > self.max_cache_size:
            self._evict_lru(audio_size)

        # 编码并存储
        encoded = base64.b64encode(audio_data)
        self.redis.setex(key, self.ttl, encoded)

        # 存储元数据
        self.redis.hset(f"{key}:stats", mapping={
            "text_length": len(text),
            "audio_size": audio_size,
            "created_at": self._get_timestamp(),
            "hits": 0
        })

        # 添加到LRU列表
        self.redis.zadd("tts:lru", {key: self._get_timestamp()})

    def _get_total_cache_size(self) -> int:
        """获取总缓存大小"""
        total = 0
        for key in self.redis.scan_iter("tts:cache:*"):
            if not key.endswith(b":stats"):
                total += self.redis.memory_usage(key) or 0
        return total

    def _evict_lru(self, needed_size: int):
        """LRU淘汰"""
        evicted_size = 0

        # 按时间戳升序获取(最久未使用)
        keys = self.redis.zrange("tts:lru", 0, -1)

        for key in keys:
            if evicted_size >= needed_size:
                break

            # 获取大小
            size = int(self.redis.hget(f"{key}:stats", "audio_size") or 0)

            # 删除
            self.redis.delete(key)
            self.redis.delete(f"{key}:stats")
            self.redis.zrem("tts:lru", key)

            evicted_size += size

        print(f"🗑️  LRU淘汰: {len(keys)}个缓存, {evicted_size/1024/1024:.2f}MB")

    def get_stats(self) -> dict:
        """获取缓存统计"""
        keys = list(self.redis.scan_iter("tts:cache:*"))
        cache_keys = [k for k in keys if not k.endswith(b":stats")]

        total_size = sum(self.redis.memory_usage(k) or 0 for k in cache_keys)
        total_hits = sum(
            int(self.redis.hget(f"{k}:stats", "hits") or 0)
            for k in cache_keys
        )

        return {
            "total_entries": len(cache_keys),
            "total_size_mb": total_size / 1024 / 1024,
            "total_hits": total_hits,
            "hit_rate": total_hits / max(len(cache_keys), 1)
        }

    def clear(self):
        """清空缓存"""
        for key in self.redis.scan_iter("tts:cache:*"):
            self.redis.delete(key)
        self.redis.delete("tts:lru")

    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        import time
        return time.time()


# 集成到 TTSService

class TTSService:
    def __init__(self):
        self.cache = TTSRedisCache(
            redis_url=settings.REDIS_URL,
            ttl_days=30,
            max_cache_size_mb=1000
        )

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """合成语音"""
        # 1. 检查缓存
        cached_audio = self.cache.get(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            format=request.format
        )

        if cached_audio:
            return TTSResponse(
                audio_base64=base64.b64encode(cached_audio).decode(),
                cached=True,
                duration_ms=self._calculate_duration(cached_audio),
                processing_time_ms=0
            )

        # 2. 合成
        start_time = time.time()

        audio_data = await self._synthesize_with_edge_tts(request)

        processing_time = (time.time() - start_time) * 1000

        # 3. 存入缓存
        self.cache.set(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            format=request.format,
            audio_data=audio_data
        )

        return TTSResponse(
            audio_base64=base64.b64encode(audio_data).decode(),
            cached=False,
            duration_ms=self._calculate_duration(audio_data),
            processing_time_ms=processing_time
        )


# 缓存管理API

@router.get("/api/v1/tts/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    return tts_service.cache.get_stats()

@router.post("/api/v1/tts/cache/clear")
async def clear_cache():
    """清空缓存"""
    tts_service.cache.clear()
    return {"message": "缓存已清空"}
```

**Grafana 监控面板**:

```python
# app/infrastructure/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# TTS缓存指标
tts_cache_hits = Counter(
    "tts_cache_hits_total",
    "TTS缓存命中次数"
)

tts_cache_misses = Counter(
    "tts_cache_misses_total",
    "TTS缓存未命中次数"
)

tts_cache_size = Gauge(
    "tts_cache_size_bytes",
    "TTS缓存总大小(字节)"
)

tts_cache_entries = Gauge(
    "tts_cache_entries_total",
    "TTS缓存条目数"
)

# 在TTSService中埋点
async def synthesize(self, request: TTSRequest):
    cached_audio = self.cache.get(...)

    if cached_audio:
        tts_cache_hits.inc()
    else:
        tts_cache_misses.inc()

    # 更新缓存指标
    stats = self.cache.get_stats()
    tts_cache_size.set(stats["total_size_mb"] * 1024 * 1024)
    tts_cache_entries.set(stats["total_entries"])
```

**验收标准**:

- [ ] 缓存命中率 > 40%
- [ ] 缓存命中时延迟 < 50ms
- [ ] LRU 淘汰机制正常
- [ ] Redis 内存使用 < 1GB
- [ ] 统计数据准确

**工作量**: 2 天

---

#### 3. VAD 升级 - Silero VAD

**参考**: [voicehelper 项目已实现]

**当前问题**: 现有 VAD 使用 Silero,但配置不够精细

**优化方案**:

```python
# app/services/vad_service_v2.py

import torch
import numpy as np
from typing import List, Dict, Tuple

class SileroVADService:
    """Silero VAD 增强版"""

    def __init__(
        self,
        model_path: str = None,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        max_speech_duration_s: float = float('inf'),
        min_silence_duration_ms: int = 100,
        window_size_samples: int = 512,
        speech_pad_ms: int = 30
    ):
        # 加载模型
        if model_path:
            self.model = torch.jit.load(model_path)
        else:
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )

        self.model.eval()

        # 参数
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.max_speech_duration_s = max_speech_duration_s
        self.min_silence_duration_ms = min_silence_duration_ms
        self.window_size_samples = window_size_samples
        self.speech_pad_ms = speech_pad_ms

        # 采样率
        self.sample_rate = 16000

    async def detect_voice_activity(
        self,
        audio_data: bytes,
        return_timestamps: bool = True
    ) -> Dict:
        """检测语音活动"""

        # 转换音频
        audio_array = self._bytes_to_float32(audio_data)

        # 归一化
        audio_tensor = torch.from_numpy(audio_array)

        # VAD检测
        speech_timestamps = self._get_speech_timestamps(
            audio_tensor,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            max_speech_duration_s=self.max_speech_duration_s,
            min_silence_duration_ms=self.min_silence_duration_ms,
            window_size_samples=self.window_size_samples,
            speech_pad_ms=self.speech_pad_ms
        )

        # 计算统计信息
        total_duration_ms = len(audio_array) / self.sample_rate * 1000
        speech_duration_ms = sum(
            (ts['end'] - ts['start']) / self.sample_rate * 1000
            for ts in speech_timestamps
        )
        speech_ratio = speech_duration_ms / total_duration_ms if total_duration_ms > 0 else 0

        result = {
            "has_speech": len(speech_timestamps) > 0,
            "speech_ratio": speech_ratio,
            "total_duration_ms": total_duration_ms,
            "speech_duration_ms": speech_duration_ms,
            "speech_segments_count": len(speech_timestamps)
        }

        if return_timestamps:
            result["timestamps"] = [
                {
                    "start_ms": ts['start'] / self.sample_rate * 1000,
                    "end_ms": ts['end'] / self.sample_rate * 1000,
                    "duration_ms": (ts['end'] - ts['start']) / self.sample_rate * 1000
                }
                for ts in speech_timestamps
            ]

        return result

    def _get_speech_timestamps(
        self,
        audio: torch.Tensor,
        **kwargs
    ) -> List[Dict]:
        """获取语音时间戳"""

        # 使用滑动窗口
        num_samples = len(audio)
        num_windows = num_samples // self.window_size_samples

        # 计算每个窗口的语音概率
        speech_probs = []

        for i in range(num_windows):
            start = i * self.window_size_samples
            end = start + self.window_size_samples

            chunk = audio[start:end]

            with torch.no_grad():
                prob = self.model(chunk.unsqueeze(0), self.sample_rate).item()

            speech_probs.append({
                'start': start,
                'end': end,
                'probability': prob
            })

        # 根据阈值筛选
        speech_chunks = [
            chunk for chunk in speech_probs
            if chunk['probability'] >= self.threshold
        ]

        # 合并连续的语音块
        timestamps = []
        if speech_chunks:
            current_start = speech_chunks[0]['start']
            current_end = speech_chunks[0]['end']

            for chunk in speech_chunks[1:]:
                gap_ms = (chunk['start'] - current_end) / self.sample_rate * 1000

                if gap_ms <= self.min_silence_duration_ms:
                    # 合并
                    current_end = chunk['end']
                else:
                    # 保存当前段
                    duration_ms = (current_end - current_start) / self.sample_rate * 1000
                    if duration_ms >= self.min_speech_duration_ms:
                        timestamps.append({
                            'start': current_start,
                            'end': current_end
                        })

                    # 开始新段
                    current_start = chunk['start']
                    current_end = chunk['end']

            # 保存最后一段
            duration_ms = (current_end - current_start) / self.sample_rate * 1000
            if duration_ms >= self.min_speech_duration_ms:
                timestamps.append({
                    'start': current_start,
                    'end': current_end
                })

        return timestamps

    def _bytes_to_float32(self, audio_bytes: bytes) -> np.ndarray:
        """字节转float32音频数组"""
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        return audio_float32


# API端点

@router.post("/api/v1/vad/detect/v2")
async def detect_vad_v2(request: VADRequest):
    """VAD检测 (Silero增强版)"""

    result = await vad_service_v2.detect_voice_activity(
        audio_data=base64.b64decode(request.audio_base64),
        return_timestamps=request.return_timestamps
    )

    return result
```

**配置优化**:

```yaml
# config/voice-engine.yaml

vad:
  provider: 'silero' # "silero" or "webrtc"

  silero:
    model_path: 'models/silero_vad.jit'
    threshold: 0.5 # 0.0-1.0, 越高越严格
    min_speech_duration_ms: 250 # 最短语音段
    max_speech_duration_s: 30 # 最长语音段
    min_silence_duration_ms: 100 # 最短静音段
    window_size_samples: 512 # 窗口大小
    speech_pad_ms: 30 # 语音段padding
```

**验收标准**:

- [ ] VAD 准确率 > 95%
- [ ] 检测延迟 < 200ms
- [ ] 支持自定义阈值
- [ ] 时间戳精确到 10ms

**工作量**: 2 天

---

#### 4. Azure Speech SDK 集成

**文件**:

- `app/services/tts_service.py:132`
- `app/services/asr_service.py:190`

**问题描述**:

```python
# TODO: 实现 Azure Speech SDK 集成
```

**影响**: 缺少备用语音服务提供商

**详细设计方案**:

```python
# app/services/azure_speech_service.py

import azure.cognitiveservices.speech as speechsdk
from typing import Optional, List
import asyncio

class AzureSpeechService:
    """Azure 语音服务"""

    def __init__(
        self,
        subscription_key: str,
        region: str = "eastasia"
    ):
        self.subscription_key = subscription_key
        self.region = region

        # ASR配置
        self.speech_config = speechsdk.SpeechConfig(
            subscription=subscription_key,
            region=region
        )

        # TTS配置
        self.tts_config = speechsdk.SpeechConfig(
            subscription=subscription_key,
            region=region
        )

    async def recognize_from_bytes(
        self,
        audio_data: bytes,
        language: str = "zh-CN"
    ) -> dict:
        """ASR识别"""

        # 设置语言
        self.speech_config.speech_recognition_language = language

        # 从字节流创建音频配置
        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1
        )

        # 创建推送流
        push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        push_stream.write(audio_data)
        push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        # 创建识别器
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=audio_config
        )

        # 同步识别
        result = speech_recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return {
                "text": result.text,
                "confidence": result.json.get("NBest", [{}])[0].get("Confidence", 0),
                "language": language,
                "duration_ms": result.duration.total_seconds() * 1000
            }

        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {
                "text": "",
                "error": "未识别到语音"
            }

        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            return {
                "text": "",
                "error": f"识别取消: {cancellation.reason}, {cancellation.error_details}"
            }

    async def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "0%",
        pitch: str = "0%"
    ) -> bytes:
        """TTS合成"""

        # 设置语音
        self.tts_config.speech_synthesis_voice_name = voice

        # 构建SSML
        ssml = f"""
        <speak version='1.0' xml:lang='zh-CN'>
            <voice name='{voice}'>
                <prosody rate='{rate}' pitch='{pitch}'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """

        # 创建合成器
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.tts_config,
            audio_config=None  # 使用内存流
        )

        # 合成
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data

        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            raise Exception(f"合成失败: {cancellation.reason}, {cancellation.error_details}")


# 多厂商适配器

from enum import Enum

class SpeechProvider(str, Enum):
    WHISPER = "whisper"
    AZURE = "azure"
    EDGE_TTS = "edge_tts"

class MultiProviderSpeechService:
    """多厂商语音服务适配器"""

    def __init__(self):
        # 初始化各厂商服务
        self.whisper = WhisperASRService()
        self.azure = AzureSpeechService(
            subscription_key=settings.AZURE_SPEECH_KEY,
            region=settings.AZURE_SPEECH_REGION
        )
        self.edge_tts = EdgeTTSService()

        # 默认提供商
        self.default_asr_provider = SpeechProvider.WHISPER
        self.default_tts_provider = SpeechProvider.EDGE_TTS

    async def recognize(
        self,
        audio_data: bytes,
        provider: Optional[SpeechProvider] = None,
        **kwargs
    ) -> dict:
        """ASR识别 (自动降级)"""

        provider = provider or self.default_asr_provider

        try:
            if provider == SpeechProvider.WHISPER:
                return await self.whisper.recognize_from_bytes(audio_data, **kwargs)

            elif provider == SpeechProvider.AZURE:
                return await self.azure.recognize_from_bytes(audio_data, **kwargs)

            else:
                raise ValueError(f"不支持的ASR提供商: {provider}")

        except Exception as e:
            print(f"⚠️  {provider} ASR失败: {e}, 尝试降级")

            # 降级策略
            if provider == SpeechProvider.AZURE:
                return await self.whisper.recognize_from_bytes(audio_data, **kwargs)
            else:
                raise

    async def synthesize(
        self,
        text: str,
        provider: Optional[SpeechProvider] = None,
        **kwargs
    ) -> bytes:
        """TTS合成 (自动降级)"""

        provider = provider or self.default_tts_provider

        try:
            if provider == SpeechProvider.EDGE_TTS:
                return await self.edge_tts.synthesize(text, **kwargs)

            elif provider == SpeechProvider.AZURE:
                return await self.azure.synthesize(text, **kwargs)

            else:
                raise ValueError(f"不支持的TTS提供商: {provider}")

        except Exception as e:
            print(f"⚠️  {provider} TTS失败: {e}, 尝试降级")

            # 降级策略
            if provider == SpeechProvider.AZURE:
                return await self.edge_tts.synthesize(text, **kwargs)
            else:
                raise


# API更新

@router.post("/api/v1/asr/recognize")
async def recognize_speech(request: ASRRequest):
    """ASR识别 (多厂商支持)"""

    result = await multi_provider_service.recognize(
        audio_data=base64.b64decode(request.audio_base64),
        provider=request.provider,  # 新增字段
        language=request.language
    )

    return ASRResponse(**result)
```

**配置**:

```bash
# .env

# Azure Speech Service
AZURE_SPEECH_KEY=your_azure_key
AZURE_SPEECH_REGION=eastasia

# 默认提供商
DEFAULT_ASR_PROVIDER=whisper  # whisper, azure
DEFAULT_TTS_PROVIDER=edge_tts  # edge_tts, azure
```

**验收标准**:

- [ ] Azure ASR 识别正常
- [ ] Azure TTS 合成正常
- [ ] 自动降级机制生效
- [ ] 多厂商切换无缝

**工作量**: 2-3 天

---

### P1 级别 (重要功能)

#### 5. 音频降噪与增强

**文件**: `main.py:261,264`

**问题描述**:

```python
# TODO: 实现降噪
# TODO: 实现音频增强
```

**技术方案**:

```python
# app/services/audio_enhancement.py

import noisereduce as nr
import librosa
import numpy as np
import scipy.signal as signal

class AudioEnhancementService:
    """音频增强服务"""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    async def enhance(
        self,
        audio_data: bytes,
        enable_denoise: bool = True,
        enable_normalization: bool = True,
        enable_equalization: bool = True
    ) -> bytes:
        """音频增强"""

        # 转换为numpy数组
        audio_array = self._bytes_to_float32(audio_data)

        # 1. 降噪
        if enable_denoise:
            audio_array = self._reduce_noise(audio_array)

        # 2. 归一化
        if enable_normalization:
            audio_array = self._normalize_volume(audio_array)

        # 3. 均衡器
        if enable_equalization:
            audio_array = self._apply_eq(audio_array)

        # 转回字节
        return self._float32_to_bytes(audio_array)

    def _reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """降噪"""
        # 使用noisereduce库
        # 自动检测噪声
        return nr.reduce_noise(
            y=audio,
            sr=self.sample_rate,
            stationary=True,
            prop_decrease=0.8
        )

    def _normalize_volume(self, audio: np.ndarray) -> np.ndarray:
        """音量归一化"""
        # 计算RMS
        rms = np.sqrt(np.mean(audio ** 2))

        if rms > 0:
            # 归一化到 -3dB
            target_rms = 0.7
            gain = target_rms / rms
            audio = audio * gain

        # 限幅
        audio = np.clip(audio, -1.0, 1.0)

        return audio

    def _apply_eq(self, audio: np.ndarray) -> np.ndarray:
        """语音均衡器"""
        # 高通滤波器 (去除低频噪声)
        sos = signal.butter(4, 80, 'hp', fs=self.sample_rate, output='sos')
        audio = signal.sosfilt(sos, audio)

        # 增强中频 (语音主要频段 300-3400Hz)
        # 这里简化处理,实际可使用参数EQ

        return audio
```

**工作量**: 2-3 天

---

#### 6. 语音克隆 (可选)

**文件**: `app/core/tts_engine.py:347`

**问题描述**:

```python
# TODO: 实现语音克隆(使用 YourTTS, Coqui TTS 等)
```

**技术方案**:

```python
# app/services/voice_cloning_service.py

from TTS.api import TTS
import torch

class VoiceCloningService:
    """语音克隆服务"""

    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        self.tts = TTS(model_name).to("cuda" if torch.cuda.is_available() else "cpu")

    async def clone_voice(
        self,
        text: str,
        reference_audio_path: str,
        language: str = "zh-cn"
    ) -> bytes:
        """克隆语音"""

        output_path = "/tmp/cloned_voice.wav"

        self.tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=reference_audio_path,
            language=language
        )

        with open(output_path, "rb") as f:
            return f.read()
```

**工作量**: 3-5 天 (需 GPU)

---

## 📈 后续迭代计划

### Sprint 1: 核心功能补全 (Week 1-2)

#### 任务清单

| 任务              | 优先级 | 工作量 | 负责人        | 状态      |
| ----------------- | ------ | ------ | ------------- | --------- |
| 流式 ASR 识别     | P0     | 3-4 天 | Backend Eng 1 | 📝 待开始 |
| TTS Redis 缓存    | P0     | 2 天   | Backend Eng 2 | 📝 待开始 |
| VAD 优化 (Silero) | P0     | 2 天   | AI Engineer   | 📝 待开始 |

#### 验收标准

- [ ] WebSocket 流式 ASR 可用
- [ ] TTS 缓存命中率 > 40%
- [ ] VAD 准确率 > 95%

---

### Sprint 2: 多厂商与增强 (Week 3-4)

#### 任务清单

| 任务              | 优先级 | 工作量 | 负责人        | 状态      |
| ----------------- | ------ | ------ | ------------- | --------- |
| Azure Speech 集成 | P0     | 2-3 天 | Backend Eng 1 | 📝 待开始 |
| 音频降噪增强      | P1     | 2-3 天 | AI Engineer   | 📝 待开始 |
| 音频时长计算      | P1     | 0.5 天 | Backend Eng 2 | 📝 待开始 |

#### 验收标准

- [ ] Azure ASR/TTS 可用
- [ ] 降噪效果明显改善
- [ ] 自动降级机制生效

---

### Sprint 3: 高级功能 (Week 5-6)

#### 任务清单

| 任务            | 优先级 | 工作量 | 负责人          | 状态      |
| --------------- | ------ | ------ | --------------- | --------- |
| 语音克隆 (可选) | P2     | 3-5 天 | AI Engineer     | 📝 待规划 |
| 全双工对话      | P1     | 5-7 天 | Backend Eng 1+2 | 📝 待规划 |
| 情感识别        | P2     | 4-5 天 | AI Engineer     | 📝 待规划 |

---

## 🎯 业界对比

### 与 voicehelper 对比

| 功能       | voicehelper | 本项目当前 | 本项目目标    |
| ---------- | ----------- | ---------- | ------------- |
| Silero VAD | ✅          | ✅         | ✅ 优化       |
| 流式 ASR   | ✅          | ❌         | ✅ 实现       |
| TTS 缓存   | ❌          | ❌         | ✅ Redis      |
| 多厂商支持 | ⚠️          | ⚠️         | ✅ Azure      |
| 情感识别   | ✅          | ❌         | ✅ (Sprint 3) |

---

## 📊 成功指标

| 指标           | 当前  | 目标 (Sprint 1) | 目标 (Sprint 3) |
| -------------- | ----- | --------------- | --------------- |
| ASR 准确率     | ~85%  | > 90%           | > 95%           |
| TTS 缓存命中率 | 0%    | > 40%           | > 60%           |
| VAD 准确率     | ~85%  | > 95%           | > 98%           |
| 平均 ASR 延迟  | ~1.5s | < 1.0s          | < 500ms         |
| 平均 TTS 延迟  | ~1.2s | < 500ms         | < 300ms         |

---

**文档版本**: v1.0.0
**最后更新**: 2025-10-27
**下次更新**: Sprint 1 结束后
