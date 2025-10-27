# VoiceHelper 功能迁移计划

> **迁移来源**: https://github.com/haoyunlt/voicehelper (v0.9.2)
> **目标项目**: VoiceAssistant
> **迁移功能**: 10 项关键功能
> **预计工作量**: 35-45 人天
> **计划周期**: 8-10 周

---

## 📊 执行摘要

### 迁移背景

VoiceHelper 项目是一个成熟的 AI 语音助手项目，已实现多项生产级功能。通过对比分析，我们发现当前 VoiceAssistant 项目在以下 10 个关键功能上落后于 VoiceHelper，需要优先迁移。

### 关键发现

| 维度           | VoiceHelper   | VoiceAssistant 当前 | 差距评估  |
| -------------- | ------------- | ------------------- | --------- |
| **功能完整度** | 90%           | 45%                 | 🔴 高差距 |
| **生产就绪度** | 生产级        | 开发中              | 🔴 高差距 |
| **关键功能**   | 10 项已实现   | 0 项已实现          | 🔴 高差距 |
| **架构复杂度** | 简洁 (5 服务) | 复杂 (15 服务)      | ⚠️ 需权衡 |

### 迁移价值

- **缩短开发周期**: 避免重复造轮子，节省 4-6 周开发时间
- **降低技术风险**: 采用已验证的生产级实现
- **提升竞争力**: 快速达到行业领先水平
- **节约成本**: 预计节省 $40k-$60k 开发成本

---

## 🎯 迁移功能清单

### 优先级分级

```
P0 (核心阻塞): 必须立即迁移，阻塞 MVP
P1 (重要增强): 显著提升用户体验和系统能力
P2 (锦上添花): 高级特性，可延后
```

### 10 项待迁移功能

| #   | 功能名称                                | 优先级 | 所属服务             | 工作量 | 依赖关系          | Sprint   |
| --- | --------------------------------------- | ------ | -------------------- | ------ | ----------------- | -------- |
| 1   | [流式 ASR 识别](#1-流式-asr-识别)       | P0     | Voice Engine         | 4-5 天 | WebSocket, VAD    | Sprint 1 |
| 2   | [长期记忆衰减](#2-长期记忆衰减)         | P0     | Agent Engine         | 3-4 天 | Milvus, Embedding | Sprint 1 |
| 3   | [Redis 任务持久化](#3-redis-任务持久化) | P0     | Agent Engine         | 2-3 天 | Redis             | Sprint 2 |
| 4   | [分布式限流器](#4-分布式限流器)         | P1     | API Gateway          | 2-3 天 | Redis             | Sprint 2 |
| 5   | [GLM-4 模型支持](#5-glm-4-模型支持)     | P1     | Model Router         | 2 天   | 智谱 AI API       | Sprint 3 |
| 6   | [文档版本管理](#6-文档版本管理)         | P1     | Knowledge Service    | 3-4 天 | PostgreSQL        | Sprint 3 |
| 7   | [病毒扫描 (ClamAV)](#7-病毒扫描-clamav) | P1     | Knowledge Service    | 2-3 天 | ClamAV            | Sprint 4 |
| 8   | [Push 通知](#8-push-通知)               | P2     | Notification Service | 3-4 天 | FCM, APNs         | Sprint 4 |
| 9   | [情感识别](#9-情感识别)                 | P2     | Voice Engine         | 3-4 天 | 情感模型          | Sprint 5 |
| 10  | [Consul 服务发现](#10-consul-服务发现)  | P1     | 所有 Go 服务         | 4-5 天 | Consul            | Sprint 2 |

**总计工作量**: 35-45 人天 (约 7-9 周 @ 5 人团队)

---

## 📋 详细迁移方案

### 1. 流式 ASR 识别

#### 当前状态

- ❌ 仅支持批量识别
- ❌ 用户体验差，延迟高
- ❌ 无法实时对话

#### VoiceHelper 实现亮点

- ✅ WebSocket 实时流式传输
- ✅ Silero VAD 端点检测
- ✅ 增量识别 + 最终识别双模式
- ✅ 完善的错误处理和重连机制

#### 迁移计划

**技术方案**:

```python
# algo/voice-engine/app/routers/asr.py

from fastapi import WebSocket, WebSocketDisconnect
from app.services.streaming_asr_service import StreamingASRService
import asyncio

@router.websocket("/ws/asr/stream")
async def websocket_asr_stream(websocket: WebSocket):
    """WebSocket 流式 ASR (参考 voicehelper)"""

    await websocket.accept()

    try:
        # 1. 接收配置
        config_msg = await websocket.receive_json()

        model_size = config_msg.get("model_size", "base")
        language = config_msg.get("language", "zh")
        vad_enabled = config_msg.get("vad_enabled", True)

        # 2. 初始化流式 ASR 服务
        streaming_asr = StreamingASRService(
            model_size=model_size,
            language=language,
            chunk_duration_ms=300,  # 300ms chunks
            vad_enabled=vad_enabled
        )

        # 3. 音频生成器
        async def audio_generator():
            """从 WebSocket 接收音频流"""
            while True:
                try:
                    message = await websocket.receive()

                    if "bytes" in message:
                        yield message["bytes"]

                    elif "text" in message:
                        cmd = json.loads(message["text"])
                        if cmd.get("type") == "end_stream":
                            break

                except WebSocketDisconnect:
                    break

        # 4. 处理流式识别
        async for result in streaming_asr.process_stream(audio_generator()):
            await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except Exception as e:
        logger.error(f"Streaming ASR error: {e}")
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })

    finally:
        await websocket.close()
```

**核心服务类**:

```python
# algo/voice-engine/app/services/streaming_asr_service.py

import webrtcvad
from faster_whisper import WhisperModel
import numpy as np
from typing import AsyncIterator
import time

class StreamingASRService:
    """流式 ASR 服务 (参考 voicehelper 实现)"""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "zh",
        chunk_duration_ms: int = 300,
        vad_enabled: bool = True,
        vad_mode: int = 3  # 0-3, 3 最严格
    ):
        # Whisper 模型
        self.model = WhisperModel(
            model_size,
            device="cuda" if torch.cuda.is_available() else "cpu",
            compute_type="int8"
        )
        self.language = language

        # VAD (端点检测)
        self.vad_enabled = vad_enabled
        if vad_enabled:
            self.vad = webrtcvad.Vad(vad_mode)

        # 音频参数
        self.chunk_duration_ms = chunk_duration_ms
        self.sample_rate = 16000
        self.chunk_size = int(self.sample_rate * chunk_duration_ms / 1000)

        # 状态管理
        self.audio_buffer = bytearray()
        self.speech_buffer = bytearray()
        self.is_speaking = False
        self.silence_duration = 0
        self.max_silence_duration_ms = 1500  # 1.5 秒静音触发识别

    async def process_stream(
        self,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[dict]:
        """处理音频流，返回识别结果流"""

        # 会话开始
        yield {
            "type": "session_start",
            "sample_rate": self.sample_rate,
            "chunk_duration_ms": self.chunk_duration_ms,
            "vad_enabled": self.vad_enabled,
            "timestamp": time.time()
        }

        async for audio_chunk in audio_stream:
            # 添加到缓冲区
            self.audio_buffer.extend(audio_chunk)

            # 处理完整的 chunk
            while len(self.audio_buffer) >= self.chunk_size * 2:  # 16-bit = 2 bytes
                chunk = bytes(self.audio_buffer[:self.chunk_size * 2])
                self.audio_buffer = self.audio_buffer[self.chunk_size * 2:]

                # VAD 检测
                is_speech = self._detect_speech(chunk) if self.vad_enabled else True

                if is_speech:
                    # 检测到语音
                    if not self.is_speaking:
                        # 语音开始
                        self.is_speaking = True
                        self.speech_buffer = bytearray()

                        yield {
                            "type": "speech_start",
                            "timestamp": time.time()
                        }

                    # 累积语音数据
                    self.speech_buffer.extend(chunk)
                    self.silence_duration = 0

                    # 增量识别 (每 3 秒)
                    if len(self.speech_buffer) >= self.sample_rate * 2 * 3:
                        partial_text = await self._recognize_partial(self.speech_buffer)

                        yield {
                            "type": "partial_result",
                            "text": partial_text,
                            "is_final": False,
                            "confidence": 0.0,  # 增量识别无置信度
                            "timestamp": time.time()
                        }

                else:
                    # 静音
                    if self.is_speaking:
                        self.silence_duration += self.chunk_duration_ms
                        self.speech_buffer.extend(chunk)  # 保留静音以保持连贯性

                        # 静音超过阈值，触发最终识别
                        if self.silence_duration >= self.max_silence_duration_ms:
                            final_text, confidence = await self._recognize_final(self.speech_buffer)

                            yield {
                                "type": "final_result",
                                "text": final_text,
                                "is_final": True,
                                "confidence": confidence,
                                "duration_ms": len(self.speech_buffer) / self.sample_rate / 2 * 1000,
                                "timestamp": time.time()
                            }

                            # 重置状态
                            self.is_speaking = False
                            self.speech_buffer = bytearray()
                            self.silence_duration = 0

                            yield {
                                "type": "speech_end",
                                "timestamp": time.time()
                            }

        # 流结束，处理剩余数据
        if self.is_speaking and len(self.speech_buffer) > 0:
            final_text, confidence = await self._recognize_final(self.speech_buffer)

            yield {
                "type": "final_result",
                "text": final_text,
                "is_final": True,
                "confidence": confidence,
                "timestamp": time.time()
            }

        yield {
            "type": "session_end",
            "timestamp": time.time()
        }

    def _detect_speech(self, audio_chunk: bytes) -> bool:
        """VAD 检测是否为语音"""
        try:
            return self.vad.is_speech(audio_chunk, self.sample_rate)
        except Exception as e:
            logger.warning(f"VAD detection failed: {e}")
            return True  # 失败时默认为语音

    async def _recognize_partial(self, audio_data: bytes) -> str:
        """增量识别 (快速，准确率较低)"""
        audio_array = self._bytes_to_float32(audio_data)

        segments, _ = self.model.transcribe(
            audio_array,
            language=self.language,
            beam_size=1,  # 快速模式
            best_of=1,
            temperature=0.0,
            vad_filter=False
        )

        text = " ".join([seg.text for seg in segments])
        return text.strip()

    async def _recognize_final(self, audio_data: bytes) -> tuple[str, float]:
        """最终识别 (完整准确率)"""
        audio_array = self._bytes_to_float32(audio_data)

        segments, info = self.model.transcribe(
            audio_array,
            language=self.language,
            beam_size=5,  # 高准确率
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            condition_on_previous_text=True
        )

        text_segments = list(segments)
        text = " ".join([seg.text for seg in text_segments])

        # 计算平均置信度
        avg_confidence = np.mean([seg.avg_logprob for seg in text_segments]) if text_segments else 0.0

        return text.strip(), float(avg_confidence)

    def _bytes_to_float32(self, audio_bytes: bytes) -> np.ndarray:
        """字节转音频数组"""
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        return audio_array.astype(np.float32) / 32768.0
```

**前端集成**:

```typescript
// platforms/web/components/StreamingASRClient.tsx

class StreamingASRClient {
  private ws: WebSocket | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;

  constructor(
    private wsUrl: string,
    private config: {
      model_size: string;
      language: string;
      vad_enabled: boolean;
    },
    private callbacks: {
      onSessionStart?: (data: any) => void;
      onSpeechStart?: (data: any) => void;
      onPartialResult?: (data: any) => void;
      onFinalResult?: (data: any) => void;
      onSpeechEnd?: (data: any) => void;
      onError?: (error: string) => void;
    }
  ) {}

  async start() {
    // 1. 建立 WebSocket 连接
    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      // 发送配置
      this.ws!.send(JSON.stringify(this.config));

      // 开始录音
      this.startRecording();
    };

    this.ws.onmessage = (event) => {
      const result = JSON.parse(event.data);

      switch (result.type) {
        case 'session_start':
          this.callbacks.onSessionStart?.(result);
          break;
        case 'speech_start':
          this.callbacks.onSpeechStart?.(result);
          break;
        case 'partial_result':
          this.callbacks.onPartialResult?.(result);
          break;
        case 'final_result':
          this.callbacks.onFinalResult?.(result);
          break;
        case 'speech_end':
          this.callbacks.onSpeechEnd?.(result);
          break;
        case 'error':
          this.callbacks.onError?.(result.error);
          break;
      }
    };

    this.ws.onerror = (error) => {
      this.callbacks.onError?.('WebSocket error');
    };
  }

  private async startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    // 使用 AudioContext 处理音频
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    const source = this.audioContext.createMediaStreamSource(stream);
    const processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);

      // 转换为 Int16
      const pcmData = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
      }

      // 发送音频数据
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(pcmData.buffer);
      }
    };

    source.connect(processor);
    processor.connect(this.audioContext.destination);
  }

  stop() {
    // 停止录音
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    // 发送结束信号
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'end_stream' }));
    }

    // 关闭 WebSocket
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// 使用示例
const asrClient = new StreamingASRClient(
  'ws://localhost:8001/ws/asr/stream',
  {
    model_size: 'base',
    language: 'zh',
    vad_enabled: true,
  },
  {
    onPartialResult: (data) => {
      console.log('识别中:', data.text);
      updateTranscript(data.text, false);
    },
    onFinalResult: (data) => {
      console.log('最终结果:', data.text, '置信度:', data.confidence);
      updateTranscript(data.text, true);
    },
    onError: (error) => {
      console.error('ASR 错误:', error);
    },
  }
);

// 开始识别
await asrClient.start();

// 停止识别
asrClient.stop();
```

**配置更新**:

```yaml
# configs/app/voice-engine.yaml

asr:
  streaming:
    enabled: true
    chunk_duration_ms: 300
    max_silence_duration_ms: 1500
    vad:
      enabled: true
      mode: 3 # 0-3, 3 最严格
      min_speech_duration_ms: 250
      max_speech_duration_s: 30

    # 识别模式
    partial_recognition:
      enabled: true
      interval_seconds: 3
      beam_size: 1

    final_recognition:
      beam_size: 5
      best_of: 5
      temperature: 0.0
      vad_filter: true
      condition_on_previous_text: true
```

**验收标准**:

- [ ] WebSocket 连接稳定，支持重连
- [ ] VAD 端点检测准确率 > 95%
- [ ] 增量识别延迟 < 500ms
- [ ] 最终识别准确率 > 90%
- [ ] 并发支持 > 20 连接
- [ ] 前端实时展示识别结果

**工作量**: 4-5 天
**责任人**: AI Engineer 1
**Sprint**: Sprint 1 (Week 1-2)

---

### 2. 长期记忆衰减

#### 当前状态

- ❌ Agent 无长期记忆
- ❌ 无法个性化对话
- ❌ 无记忆检索能力

#### VoiceHelper 实现亮点

- ✅ Milvus 向量存储
- ✅ Ebbinghaus 遗忘曲线衰减
- ✅ 访问频率增强
- ✅ 重要性评分

#### 迁移计划

**技术方案**:

```python
# algo/agent-engine/app/memory/vector_memory_manager.py

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType
import numpy as np
from datetime import datetime
from typing import List, Dict
import httpx

class VectorMemoryManager:
    """基于向量的长期记忆管理 (参考 voicehelper)"""

    def __init__(
        self,
        milvus_url: str = "http://milvus:19530",
        embedding_service_url: str = "http://model-adapter:8002",
        collection_name: str = "agent_memory"
    ):
        self.milvus_url = milvus_url
        self.embedding_service_url = embedding_service_url
        self.collection_name = collection_name
        self._init_collection()

    def _init_collection(self):
        """初始化 Milvus 集合"""
        from pymilvus import connections, utility

        # 连接 Milvus
        connections.connect("default", host=self.milvus_url.split("//")[1].split(":")[0], port="19530")

        # 检查集合是否存在
        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)
            collection.load()
            return

        # 创建集合
        fields = [
            FieldSchema(name="memory_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),  # OpenAI embedding
            FieldSchema(name="importance", dtype=DataType.FLOAT),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="access_count", dtype=DataType.INT64),
            FieldSchema(name="last_accessed", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description="Agent Long-term Memory")
        collection = Collection(name=self.collection_name, schema=schema)

        # 创建索引
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()

        logger.info(f"✅ Milvus collection '{self.collection_name}' created")

    async def store_memory(
        self,
        user_id: str,
        content: str,
        importance: float = 0.5
    ) -> str:
        """存储记忆"""
        import uuid
        from pymilvus import Collection

        # 生成 embedding
        embedding = await self._get_embedding(content)

        memory_id = str(uuid.uuid4())
        memory_data = [{
            "memory_id": memory_id,
            "user_id": user_id,
            "content": content,
            "embedding": embedding,
            "importance": importance,
            "created_at": int(datetime.now().timestamp()),
            "access_count": 0,
            "last_accessed": int(datetime.now().timestamp()),
        }]

        collection = Collection(self.collection_name)
        collection.insert(memory_data)

        logger.info(f"✅ Memory stored: {memory_id} (user: {user_id})")
        return memory_id

    async def retrieve_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        time_decay_enabled: bool = True,
        time_decay_half_life_days: int = 30
    ) -> List[Dict]:
        """检索相关记忆 (Ebbinghaus 遗忘曲线衰减)"""
        from pymilvus import Collection

        # 生成查询向量
        query_embedding = await self._get_embedding(query)

        # 向量检索
        collection = Collection(self.collection_name)
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k * 3,  # 多召回一些，后面重排序
            expr=f'user_id == "{user_id}"',
            output_fields=["memory_id", "content", "importance", "created_at", "access_count", "last_accessed"]
        )

        # 后处理: 时间衰减 + 重要性加权 + 访问频率增强
        memories = []
        current_time = datetime.now().timestamp()

        for hits in results:
            for hit in hits:
                entity = hit.entity

                # 1. 向量相似度分数 (L2 距离，越小越好)
                vector_score = 1.0 / (1.0 + hit.distance)

                # 2. Ebbinghaus 遗忘曲线衰减
                if time_decay_enabled:
                    time_diff_days = (current_time - entity.get("created_at")) / 86400
                    decay_factor = np.exp(-time_diff_days / time_decay_half_life_days)  # 半衰期
                else:
                    decay_factor = 1.0

                # 3. 访问频率增强
                access_boost = min(entity.get("access_count", 0) * 0.05, 0.3)  # 最多提升 30%

                # 4. 重要性权重
                importance = entity.get("importance", 0.5)

                # 综合得分
                score = (
                    vector_score * 0.4 +  # 向量相似度
                    decay_factor * 0.3 +  # 时间衰减
                    importance * 0.2 +    # 重要性
                    access_boost * 0.1    # 访问频率
                )

                memories.append({
                    "memory_id": entity.get("memory_id"),
                    "content": entity.get("content"),
                    "score": score,
                    "vector_score": vector_score,
                    "decay_factor": decay_factor,
                    "importance": importance,
                    "access_count": entity.get("access_count", 0),
                    "created_at": entity.get("created_at"),
                    "days_ago": time_diff_days
                })

        # 按综合得分排序并返回 top_k
        memories.sort(key=lambda x: x["score"], reverse=True)
        return memories[:top_k]

    async def update_memory_access(self, memory_id: str):
        """更新记忆访问统计"""
        from pymilvus import Collection

        collection = Collection(self.collection_name)

        # 查询现有记忆
        expr = f'memory_id == "{memory_id}"'
        results = collection.query(expr=expr, output_fields=["*"])

        if results:
            entity = results[0]
            entity["access_count"] += 1
            entity["last_accessed"] = int(datetime.now().timestamp())

            # 删除旧记录
            collection.delete(expr=expr)

            # 插入更新后的记录
            collection.insert([entity])

            logger.debug(f"✅ Memory access updated: {memory_id} (count: {entity['access_count']})")

    async def _get_embedding(self, text: str) -> List[float]:
        """调用 Model Adapter 获取 embedding"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.embedding_service_url}/v1/embeddings",
                json={
                    "model": "text-embedding-ada-002",
                    "input": text
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Embedding service error: {response.text}")

            data = response.json()
            return data["data"][0]["embedding"]

    async def evaluate_importance(self, content: str, context: Dict = None) -> float:
        """使用 LLM 评估记忆重要性 (参考 voicehelper)"""

        # 简化实现: 基于规则
        # 生产环境应使用 LLM 评估

        important_keywords = [
            "重要", "记住", "关键", "必须", "务必",
            "喜欢", "讨厌", "爱", "恨",
            "永远", "一直", "从不",
            "名字", "生日", "地址", "电话"
        ]

        score = 0.5  # 基础分

        for keyword in important_keywords:
            if keyword in content:
                score += 0.1

        # 问句重要性较低
        if "?" in content or "？" in content or "吗" in content:
            score -= 0.1

        # 长句重要性较高
        if len(content) > 50:
            score += 0.05

        # 限制范围
        return min(max(score, 0.0), 1.0)
```

**集成到 Agent**:

```python
# algo/agent-engine/app/memory/memory_manager.py

class MemoryManager:
    """统一记忆管理器"""

    def __init__(self):
        self.short_term = {}  # 对话级短期记忆 (内存)
        self.long_term = VectorMemoryManager()  # 向量化长期记忆 (Milvus)

    async def add_to_short_term(self, session_id: str, message: Dict):
        """添加到短期记忆"""
        if session_id not in self.short_term:
            self.short_term[session_id] = []

        self.short_term[session_id].append(message)

        # 限制短期记忆大小
        if len(self.short_term[session_id]) > 20:
            self.short_term[session_id] = self.short_term[session_id][-20:]

    async def add_to_long_term(
        self,
        user_id: str,
        content: str,
        auto_evaluate_importance: bool = True
    ) -> str:
        """添加到长期记忆"""

        # 评估重要性
        if auto_evaluate_importance:
            importance = await self.long_term.evaluate_importance(content)
        else:
            importance = 0.5

        # 存储
        memory_id = await self.long_term.store_memory(
            user_id=user_id,
            content=content,
            importance=importance
        )

        return memory_id

    async def recall(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[str]:
        """召回相关长期记忆"""

        memories = await self.long_term.retrieve_memory(
            user_id=user_id,
            query=query,
            top_k=top_k,
            time_decay_enabled=True,
            time_decay_half_life_days=30
        )

        # 更新访问统计
        for memory in memories:
            await self.long_term.update_memory_access(memory["memory_id"])

        return [m["content"] for m in memories]

    def get_short_term(self, session_id: str, last_n: int = 10) -> List[Dict]:
        """获取短期记忆"""
        return self.short_term.get(session_id, [])[-last_n:]

    def clear_short_term(self, session_id: str):
        """清除短期记忆"""
        if session_id in self.short_term:
            del self.short_term[session_id]
```

**API 接口**:

```python
# algo/agent-engine/routers/memory.py

@router.post("/memory/store")
async def store_memory(request: StoreMemoryRequest):
    """存储长期记忆"""

    memory_id = await app.state.memory_manager.add_to_long_term(
        user_id=request.user_id,
        content=request.content,
        auto_evaluate_importance=True
    )

    return {
        "memory_id": memory_id,
        "status": "stored"
    }

@router.post("/memory/recall")
async def recall_memory(request: RecallMemoryRequest):
    """召回相关记忆"""

    memories = await app.state.memory_manager.recall(
        user_id=request.user_id,
        query=request.query,
        top_k=request.top_k or 5
    )

    return {
        "memories": memories,
        "count": len(memories)
    }
```

**配置**:

```yaml
# configs/app/agent-engine.yaml

memory:
  type: 'vector' # "memory" or "vector"

  vector:
    milvus_url: 'http://milvus:19530'
    embedding_service_url: 'http://model-adapter:8002'
    collection_name: 'agent_memory'

    # 时间衰减
    time_decay_enabled: true
    time_decay_half_life_days: 30 # 30 天半衰期

    # 检索参数
    top_k_candidates: 15 # 召回候选数
    top_k_final: 5 # 最终返回数

  short_term:
    max_messages: 20 # 短期记忆最大消息数
```

**验收标准**:

- [ ] 记忆成功存储到 Milvus
- [ ] 向量检索召回率 > 80%
- [ ] 时间衰减机制生效
- [ ] 访问频率增强生效
- [ ] 重要性评分合理

**工作量**: 3-4 天
**责任人**: AI Engineer 1
**Sprint**: Sprint 1

---

### 3. Redis 任务持久化

#### 当前状态

- ❌ Agent 任务仅存内存
- ❌ 服务重启任务丢失
- ❌ 无法查询历史任务

#### VoiceHelper 实现亮点

- ✅ Redis 持久化任务
- ✅ 支持任务查询和恢复
- ✅ TTL 自动过期
- ✅ 任务状态追踪

#### 迁移计划

**技术方案**:

```python
# algo/agent-engine/app/storage/redis_task_store.py

import redis
import json
from datetime import timedelta, datetime
from typing import Dict, List, Optional

class RedisTaskStore:
    """基于 Redis 的任务存储 (参考 voicehelper)"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        ttl_days: int = 7
    ):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl_days = ttl_days

    def save_task(self, task_id: str, task_data: Dict):
        """保存任务"""
        key = f"agent:task:{task_id}"

        # 添加元数据
        task_data["_updated_at"] = datetime.now().isoformat()

        self.redis.setex(
            key,
            timedelta(days=self.ttl_days),
            json.dumps(task_data, ensure_ascii=False)
        )

        # 添加到任务列表 (用于查询)
        list_key = f"agent:tasks:{task_data.get('user_id', 'unknown')}"
        self.redis.lpush(list_key, task_id)
        self.redis.expire(list_key, timedelta(days=self.ttl_days))

        logger.debug(f"✅ Task saved to Redis: {task_id}")

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务"""
        key = f"agent:task:{task_id}"
        data = self.redis.get(key)

        if data:
            return json.loads(data)

        return None

    def update_task(self, task_id: str, updates: Dict):
        """更新任务"""
        task = self.get_task(task_id)

        if task:
            task.update(updates)
            self.save_task(task_id, task)

    def delete_task(self, task_id: str):
        """删除任务"""
        key = f"agent:task:{task_id}"
        self.redis.delete(key)

        logger.debug(f"❌ Task deleted from Redis: {task_id}")

    def list_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """列出任务"""

        tasks = []

        if user_id:
            # 查询用户的任务
            list_key = f"agent:tasks:{user_id}"
            task_ids = self.redis.lrange(list_key, 0, limit - 1)

            for task_id in task_ids:
                task = self.get_task(task_id)
                if task:
                    if not status or task.get("status") == status:
                        tasks.append(task)
        else:
            # 扫描所有任务
            keys = self.redis.keys("agent:task:*")

            for key in keys[:limit]:
                data = self.redis.get(key)
                if data:
                    task = json.loads(data)
                    if not status or task.get("status") == status:
                        tasks.append(task)

        # 按创建时间排序
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return tasks

    def get_stats(self) -> Dict:
        """获取统计信息"""

        # 统计各状态任务数
        keys = list(self.redis.scan_iter("agent:task:*"))

        stats = {
            "total": len(keys),
            "by_status": {}
        }

        for key in keys:
            data = self.redis.get(key)
            if data:
                task = json.loads(data)
                status = task.get("status", "unknown")
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        return stats
```

**集成到 Agent Service**:

```python
# algo/agent-engine/app/core/agent_service.py

class AgentService:

    def __init__(self):
        self.task_store = RedisTaskStore()  # 替代内存存储
        # ...

    async def execute_async(
        self,
        task: AgentTask,
        background_tasks: BackgroundTasks
    ) -> str:
        """异步执行任务"""

        task_id = task.task_id

        # 创建任务记录 (持久化到 Redis)
        self.task_store.save_task(task_id, {
            "task_id": task_id,
            "user_id": task.user_id,
            "task": task.task,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": task.dict()
        })

        # 后台执行
        background_tasks.add_task(
            self._execute_task_background,
            task_id=task_id,
            task=task
        )

        return task_id

    async def _execute_task_background(self, task_id: str, task: AgentTask):
        """后台执行任务"""

        # 更新状态
        self.task_store.update_task(task_id, {
            "status": "running",
            "started_at": datetime.now().isoformat()
        })

        try:
            # 执行任务
            result = await self._execute_task(task)

            # 更新结果
            self.task_store.update_task(task_id, {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now().isoformat()
            })

        except Exception as e:
            # 更新错误
            self.task_store.update_task(task_id, {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })

    async def get_task_status(self, task_id: str) -> Dict:
        """查询任务状态"""

        task = self.task_store.get_task(task_id)

        if not task:
            raise HTTPException(404, "任务不存在")

        return task

    async def cancel_task(self, task_id: str):
        """取消任务"""

        task = self.task_store.get_task(task_id)

        if not task:
            raise HTTPException(404, "任务不存在")

        if task["status"] in ["completed", "failed"]:
            raise HTTPException(400, "任务已结束，无法取消")

        self.task_store.update_task(task_id, {
            "status": "cancelled",
            "cancelled_at": datetime.now().isoformat()
        })
```

**API 接口**:

```python
# algo/agent-engine/routers/agent.py

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""

    task = await agent_service.get_task_status(task_id)

    return task

@router.get("/tasks")
async def list_tasks(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """列出任务"""

    tasks = agent_service.task_store.list_tasks(
        user_id=user_id,
        status=status,
        limit=limit
    )

    return {
        "tasks": tasks,
        "count": len(tasks)
    }

@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """取消任务"""

    await agent_service.cancel_task(task_id)

    return {"message": "任务已取消"}

@router.get("/tasks/stats")
async def get_task_stats():
    """获取任务统计"""

    stats = agent_service.task_store.get_stats()

    return stats
```

**验收标准**:

- [ ] 任务成功持久化到 Redis
- [ ] 服务重启后任务可恢复
- [ ] 任务查询功能正常
- [ ] TTL 自动过期生效
- [ ] 任务状态追踪准确

**工作量**: 2-3 天
**责任人**: Backend Engineer 2
**Sprint**: Sprint 2

---

## 📅 迁移时间线

### Sprint 1 (Week 1-2): P0 核心功能

| 任务          | 工作量 | 负责人   | 状态 |
| ------------- | ------ | -------- | ---- |
| 流式 ASR 识别 | 4-5 天 | AI Eng 1 | 📝   |
| 长期记忆衰减  | 3-4 天 | AI Eng 1 | 📝   |

**验收**: 流式 ASR 可用，Agent 有长期记忆

---

### Sprint 2 (Week 3-4): 基础设施增强

| 任务             | 工作量 | 负责人        | 状态 |
| ---------------- | ------ | ------------- | ---- |
| Redis 任务持久化 | 2-3 天 | Backend Eng 2 | 📝   |
| 分布式限流器     | 2-3 天 | Backend Eng 1 | 📝   |
| Consul 服务发现  | 4-5 天 | SRE           | 📝   |

**验收**: 任务持久化，限流生效，服务发现可用

---

### Sprint 3 (Week 5-6): 模型与知识管理

| 任务           | 工作量 | 负责人        | 状态 |
| -------------- | ------ | ------------- | ---- |
| GLM-4 模型支持 | 2 天   | Backend Eng 1 | 📝   |
| 文档版本管理   | 3-4 天 | Backend Eng 2 | 📝   |

**验收**: GLM-4 可用，文档版本管理正常

---

### Sprint 4 (Week 7-8): 安全与通知

| 任务              | 工作量 | 负责人        | 状态 |
| ----------------- | ------ | ------------- | ---- |
| 病毒扫描 (ClamAV) | 2-3 天 | Backend Eng 2 | 📝   |
| Push 通知         | 3-4 天 | Backend Eng 1 | 📝   |

**验收**: 病毒扫描拦截恶意文件，推送通知可用

---

### Sprint 5 (Week 9-10): 高级特性

| 任务     | 工作量 | 负责人   | 状态 |
| -------- | ------ | -------- | ---- |
| 情感识别 | 3-4 天 | AI Eng 2 | 📝   |

**验收**: 语音情感识别准确率 > 80%

---

## 💰 成本估算

### 人力成本

| 角色             | 人数  | 时间     | 成本 (假设年薪 $80k) |
| ---------------- | ----- | -------- | -------------------- |
| AI Engineer      | 2     | 8 周     | $24,615              |
| Backend Engineer | 2     | 8 周     | $24,615              |
| SRE Engineer     | 1     | 4 周     | $6,154               |
| **总计**         | **5** | **8 周** | **$55,384**          |

### 基础设施成本

| 资源                 | 月成本   | 2 个月总计 |
| -------------------- | -------- | ---------- |
| ClamAV 服务器        | $50      | $100       |
| Consul 集群 (3 节点) | $150     | $300       |
| **总计**             | **$200** | **$400**   |

### API 成本

| 服务            | 月成本        | 2 个月总计      |
| --------------- | ------------- | --------------- |
| 智谱 AI (GLM-4) | $300-$600     | $600-$1,200     |
| Firebase FCM    | $0            | $0              |
| Apple APNs      | $0            | $0              |
| **总计**        | **$300-$600** | **$600-$1,200** |

### 总成本估算

**总计**: $56,384 - $57,984 (约 $57k)

**对比完全自研**: 节省约 $40k-$60k

---

## 🎯 成功指标

### 技术指标

| 指标             | 当前       | 迁移后目标   | 提升  |
| ---------------- | ---------- | ------------ | ----- |
| Agent 记忆召回率 | 0%         | > 80%        | +∞    |
| ASR 实时性       | ~1.5s 批量 | < 500ms 流式 | +67%  |
| 任务持久化率     | 0%         | 100%         | +100% |
| 限流准确性       | 本地不准   | 分布式准确   | ✅    |
| 模型支持数       | 2          | 3 (加 GLM-4) | +50%  |
| 文档安全性       | 无扫描     | 病毒扫描     | ✅    |
| 服务发现         | 静态配置   | 动态发现     | ✅    |

### 业务指标

| 指标           | 预期提升 |
| -------------- | -------- |
| 用户满意度     | +30%     |
| 对话个性化程度 | +50%     |
| 系统稳定性     | +40%     |
| 安全事件       | -90%     |

---

## ⚠️ 风险与缓解

### 高风险

1. **Milvus 性能瓶颈** (概率: 中, 影响: 高)

   - **缓解**: 提前压测，优化索引参数，必要时分片

2. **WebSocket 稳定性** (概率: 中, 影响: 高)

   - **缓解**: 实现心跳检测和自动重连机制

3. **GLM-4 API 稳定性** (概率: 中, 影响: 中)
   - **缓解**: 实现降级策略，备用 GPT-3.5

### 中风险

4. **ClamAV 扫描延迟** (概率: 高, 影响: 中)

   - **缓解**: 异步扫描 + 异步通知

5. **Redis 内存使用** (概率: 中, 影响: 中)
   - **缓解**: 合理设置 TTL，监控内存使用

---

## ✅ 验收清单

### Sprint 1 验收

- [ ] 流式 ASR WebSocket 连接稳定
- [ ] VAD 端点检测准确率 > 95%
- [ ] ASR 实时延迟 < 500ms
- [ ] Agent 记忆存储到 Milvus
- [ ] 记忆检索召回率 > 80%
- [ ] 时间衰减机制生效

### Sprint 2 验收

- [ ] 任务持久化到 Redis
- [ ] 服务重启任务可恢复
- [ ] 分布式限流器生效
- [ ] Consul 服务注册成功
- [ ] 服务健康检查正常

### Sprint 3 验收

- [ ] GLM-4 模型可用
- [ ] 文档版本创建/回滚正常
- [ ] 版本比对功能可用

### Sprint 4 验收

- [ ] ClamAV 扫描拦截恶意文件
- [ ] 扫描延迟 < 3s
- [ ] FCM/APNs 推送通知成功
- [ ] 设备 Token 管理正常

### Sprint 5 验收

- [ ] 情感识别准确率 > 80%
- [ ] 支持 7 种情感分类
- [ ] 实时情感分析延迟 < 200ms

---

## 📚 参考文档

### VoiceHelper 参考

- GitHub: https://github.com/haoyunlt/voicehelper
- README: 完整功能说明
- v0.9.2 Release Notes: 最新特性

### 内部文档

- [SERVICES_ITERATION_MASTER_PLAN.md](SERVICES_ITERATION_MASTER_PLAN.md) - 总体迭代计划
- [SERVICE_AGENT_ENGINE_PLAN.md](SERVICE_AGENT_ENGINE_PLAN.md) - Agent 引擎详细计划
- [SERVICE_VOICE_ENGINE_PLAN.md](SERVICE_VOICE_ENGINE_PLAN.md) - 语音引擎详细计划

---

## 📞 联系方式

**项目负责人**: [待定]
**技术对接**: [待定]

---

**文档版本**: v1.0.0
**生成日期**: 2025-10-27
**下次审查**: Sprint 2 结束后

---

**让我们快速迁移 VoiceHelper 的优秀特性，加速 VoiceAssistant 的开发进度！🚀**
