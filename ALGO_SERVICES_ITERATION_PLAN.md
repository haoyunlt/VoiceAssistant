# 算法服务迭代计划（Python Services）

> **版本**: v2.0  
> **生成日期**: 2025-10-27  
> **适用服务**: Agent Engine, Voice Engine, RAG Engine, Retrieval Service, Model Adapter, Indexing Service, Multimodal Engine, Vector Store Adapter, Knowledge Service (Python)

---

## 📋 目录

- [1. Agent Engine（Agent执行引擎）](#1-agent-engine)
- [2. Voice Engine（语音引擎）](#2-voice-engine)
- [3. RAG Engine（检索增强生成引擎）](#3-rag-engine)
- [4. Retrieval Service（检索服务）](#4-retrieval-service)
- [5. Model Adapter（模型适配器）](#5-model-adapter)
- [6. Indexing Service（索引服务）](#6-indexing-service)
- [7. Multimodal Engine（多模态引擎）](#7-multimodal-engine)
- [8. Vector Store Adapter（向量存储适配器）](#8-vector-store-adapter)
- [9. Knowledge Service（知识服务-Python部分）](#9-knowledge-service)

---

## 概述

本文档汇总了所有算法服务（Python）的当前实现状态、待实现功能和详细的迭代计划。每个服务包含：

- ✅ **已实现功能清单**
- 🔄 **待完善功能**
- 🚀 **迭代计划**（包含设计方案和示例代码）
- 📊 **性能指标和验收标准**

---

## 1. Agent Engine

### 1.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| ReAct Agent执行 | ✅ 完成 | Thought-Action-Observation循环 |
| 工具管理系统 | ✅ 完成 | 内置计算器、搜索、知识库查询 |
| LLM集成 | ✅ 完成 | OpenAI API支持 |
| 任务管理 | ✅ 完成 | 同步/异步执行、状态查询 |
| Plan & Execute Agent | ✅ 完成 | 计划分解和执行 |
| 工具调用系统 | ✅ 完成 | 搜索、计算器、知识库等 |
| 记忆系统 | ✅ 完成 | 对话历史、工作记忆 |
| WebSocket支持 | ✅ 完成 | 实时交互 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | 流式响应优化 | 框架已有 | 2天 |
| P0 | 工具调用容错机制 | 部分实现 | 3天 |
| P1 | 多Agent协作 | 未实现 | 5天 |
| P1 | 人工反馈循环 | 未实现 | 4天 |
| P2 | Agent训练和优化 | 未实现 | 10天 |
| P2 | 分布式Agent执行 | 未实现 | 7天 |

### 1.2 迭代计划

#### Sprint 1: 流式响应和容错增强（1周）

**目标**: 完善流式响应，增加工具调用容错

**任务清单**:

1. **流式响应优化** (2天)

```python
# File: app/services/agent_service.py

from typing import AsyncIterator
import asyncio

class AgentService:
    async def execute_stream(
        self,
        task: AgentTask
    ) -> AsyncIterator[AgentStepResult]:
        """流式执行Agent任务，实时返回每一步结果"""
        
        # 初始化
        context = self._init_context(task)
        iteration = 0
        
        while iteration < task.max_iterations:
            # 1. Thought阶段 - 流式返回
            thought_chunk = ""
            async for chunk in self.llm_service.chat_stream(
                messages=context.messages,
                model=task.model
            ):
                thought_chunk += chunk
                yield AgentStepResult(
                    step_type="thought",
                    content=chunk,
                    is_partial=True
                )
            
            # 2. 解析Action
            action = self._parse_action(thought_chunk)
            if action is None:
                # 最终答案
                yield AgentStepResult(
                    step_type="final_answer",
                    content=thought_chunk,
                    is_partial=False
                )
                break
            
            yield AgentStepResult(
                step_type="action",
                tool_name=action.tool_name,
                parameters=action.parameters,
                is_partial=False
            )
            
            # 3. 执行Tool（带容错）
            try:
                observation = await self._execute_tool_with_retry(
                    tool_name=action.tool_name,
                    parameters=action.parameters
                )
            except ToolExecutionError as e:
                # 错误作为Observation返回
                observation = f"Error: {str(e)}"
            
            yield AgentStepResult(
                step_type="observation",
                content=observation,
                is_partial=False
            )
            
            # 4. 更新上下文
            context.add_step(thought_chunk, action, observation)
            iteration += 1
        
        yield AgentStepResult(
            step_type="completed",
            content=context.final_answer,
            is_partial=False
        )
```

2. **工具调用容错机制** (3天)

```python
# File: app/services/tool_service.py

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

class ToolService:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError))
    )
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        timeout: int = 30
    ) -> Any:
        """执行工具，带重试和超时控制"""
        
        # 1. 验证工具存在
        if tool_name not in self.tools:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found")
        
        tool = self.tools[tool_name]
        
        # 2. 参数验证
        try:
            validated_params = self._validate_parameters(tool, parameters)
        except ValidationError as e:
            raise ToolParameterError(f"Invalid parameters: {str(e)}")
        
        # 3. 执行工具（带超时）
        try:
            async with asyncio.timeout(timeout):
                result = await tool.function(**validated_params)
                return result
        except asyncio.TimeoutError:
            raise ToolTimeoutError(f"Tool '{tool_name}' timed out after {timeout}s")
        except Exception as e:
            # 记录错误日志
            logger.error(f"Tool '{tool_name}' execution failed: {str(e)}")
            raise ToolExecutionError(f"Tool execution failed: {str(e)}")
    
    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> str:
        """执行工具，失败时返回友好错误信息"""
        try:
            result = await self.execute_tool(tool_name, parameters)
            return self._format_result(result)
        except ToolNotFoundError as e:
            return f"❌ 工具不存在: {str(e)}"
        except ToolParameterError as e:
            return f"❌ 参数错误: {str(e)}"
        except ToolTimeoutError as e:
            return f"⏱️ 执行超时: {str(e)}"
        except ToolExecutionError as e:
            return f"❌ 执行失败: {str(e)}"
```

#### Sprint 2: 多Agent协作（1周）

**目标**: 实现多Agent协作模式

**设计方案**:

```python
# File: app/models/multi_agent.py

from enum import Enum
from typing import List, Dict

class AgentRole(str, Enum):
    """Agent角色"""
    COORDINATOR = "coordinator"  # 协调器
    RESEARCHER = "researcher"    # 研究员
    ANALYST = "analyst"          # 分析师
    EXECUTOR = "executor"        # 执行者

class MultiAgentTask(BaseModel):
    """多Agent任务"""
    task_id: str
    description: str
    agents: List[AgentConfig]  # 参与的Agent配置
    workflow: Dict[str, Any]   # 工作流定义
    max_rounds: int = 10       # 最大协作轮数

class AgentConfig(BaseModel):
    """Agent配置"""
    agent_id: str
    role: AgentRole
    model: str
    tools: List[str]
    system_prompt: str

# File: app/services/multi_agent_service.py

class MultiAgentService:
    """多Agent协作服务"""
    
    async def execute_multi_agent_task(
        self,
        task: MultiAgentTask
    ) -> MultiAgentResult:
        """执行多Agent协作任务"""
        
        # 1. 初始化所有Agent
        agents = {}
        for agent_config in task.agents:
            agents[agent_config.agent_id] = self._create_agent(agent_config)
        
        # 2. 获取协调器
        coordinator = agents.get("coordinator")
        if not coordinator:
            raise ValueError("Multi-agent task requires a coordinator")
        
        # 3. 协作循环
        context = MultiAgentContext()
        for round_num in range(task.max_rounds):
            # 协调器决定下一步
            next_action = await coordinator.decide_next_action(context)
            
            if next_action.type == "complete":
                break
            
            # 执行Action
            if next_action.type == "delegate":
                # 委派给其他Agent
                target_agent = agents[next_action.target_agent_id]
                result = await target_agent.execute(next_action.subtask)
                context.add_result(next_action.target_agent_id, result)
            
            elif next_action.type == "synthesize":
                # 协调器综合结果
                final_answer = await coordinator.synthesize(context)
                return MultiAgentResult(
                    answer=final_answer,
                    steps=context.steps,
                    rounds=round_num + 1
                )
        
        return MultiAgentResult(
            answer=context.get_final_answer(),
            steps=context.steps,
            rounds=task.max_rounds
        )
```

**示例工作流**:

```yaml
# 多Agent协作工作流示例
workflow:
  name: "Research and Analysis"
  agents:
    - agent_id: coordinator
      role: coordinator
      model: gpt-4
      system_prompt: "You are a coordinator managing multiple specialized agents."
    
    - agent_id: researcher
      role: researcher
      model: gpt-3.5-turbo
      tools: [search, knowledge_base]
      system_prompt: "You are a researcher. Find relevant information."
    
    - agent_id: analyst
      role: analyst
      model: gpt-4
      tools: [calculator, data_analysis]
      system_prompt: "You are an analyst. Analyze data and provide insights."
  
  steps:
    - step: 1
      agent: coordinator
      action: "Break down the task into subtasks"
    
    - step: 2
      agent: researcher
      action: "Research each subtask"
    
    - step: 3
      agent: analyst
      action: "Analyze research results"
    
    - step: 4
      agent: coordinator
      action: "Synthesize final answer"
```

#### Sprint 3: 人工反馈循环（RLHF）（1周）

**目标**: 实现人工反馈循环，持续优化Agent表现

```python
# File: app/services/feedback_service.py

from datetime import datetime

class FeedbackService:
    """人工反馈服务"""
    
    async def submit_feedback(
        self,
        task_id: str,
        user_id: str,
        rating: int,  # 1-5星
        feedback_text: Optional[str] = None,
        correct_answer: Optional[str] = None
    ) -> Feedback:
        """提交人工反馈"""
        
        feedback = Feedback(
            id=generate_id(),
            task_id=task_id,
            user_id=user_id,
            rating=rating,
            feedback_text=feedback_text,
            correct_answer=correct_answer,
            created_at=datetime.utcnow()
        )
        
        # 1. 保存反馈到数据库
        await self.feedback_repo.create(feedback)
        
        # 2. 如果评分低，标记为需要改进
        if rating <= 2:
            await self._flag_for_improvement(task_id)
        
        # 3. 如果提供了正确答案，创建训练样本
        if correct_answer:
            await self._create_training_sample(task_id, correct_answer)
        
        return feedback
    
    async def get_improvement_candidates(
        self,
        limit: int = 100
    ) -> List[TaskFeedback]:
        """获取需要改进的任务"""
        
        # 查询低评分任务
        return await self.feedback_repo.get_low_rated_tasks(
            rating_threshold=2,
            limit=limit
        )
    
    async def apply_learnings(
        self,
        task_id: str
    ):
        """应用反馈学习改进提示词"""
        
        # 1. 获取任务和反馈
        task = await self.task_repo.get(task_id)
        feedbacks = await self.feedback_repo.get_by_task(task_id)
        
        # 2. 分析失败原因
        analysis = await self._analyze_failure(task, feedbacks)
        
        # 3. 生成改进建议
        improvements = await self._generate_improvements(analysis)
        
        # 4. 更新提示词模板
        await self._update_prompt_template(task.type, improvements)
```

### 1.3 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| 平均执行时间 | ~5s | < 3s | P95 < 5s |
| 工具调用成功率 | 90% | > 95% | 错误率 < 5% |
| 并发支持 | 未测试 | > 50 | 50并发无降级 |
| 流式首字节延迟 | N/A | < 500ms | TTFB < 500ms |

---

## 2. Voice Engine

### 2.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| ASR - Faster Whisper | ✅ 完成 | 批量/文件上传识别 |
| ASR - Azure Speech | ✅ 完成 | 高精度识别，自动降级 |
| TTS - Edge TTS | ✅ 完成 | 批量/流式合成 |
| TTS - Azure Neural | ✅ 完成 | Neural语音合成 |
| VAD - Silero | ✅ 完成 | 实时语音活动检测 |
| 流式ASR | ✅ 完成 | WebSocket实时识别 |
| 智能缓存 | ✅ 完成 | TTS结果缓存 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | 说话人分离 | 未实现 | 4天 |
| P1 | 情感识别 | 未实现 | 3天 |
| P1 | 噪音抑制 | 未实现 | 3天 |
| P2 | 实时语音翻译 | 未实现 | 5天 |
| P2 | 声纹识别 | 未实现 | 7天 |

### 2.2 迭代计划

#### Sprint 1: 说话人分离（1周）

**目标**: 实现多说话人识别和分离

```python
# File: app/services/speaker_diarization_service.py

from pyannote.audio import Pipeline
import torch

class SpeakerDiarizationService:
    """说话人分离服务"""
    
    def __init__(self):
        # 加载pyannote.audio预训练模型
        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token="YOUR_HF_TOKEN"
        )
    
    async def diarize(
        self,
        audio_data: bytes,
        num_speakers: Optional[int] = None
    ) -> DiarizationResult:
        """说话人分离"""
        
        # 1. 保存临时音频文件
        temp_path = f"/tmp/audio_{generate_id()}.wav"
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        # 2. 执行说话人分离
        diarization = self.pipeline(
            temp_path,
            num_speakers=num_speakers
        )
        
        # 3. 解析结果
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(SpeakerSegment(
                start_ms=turn.start * 1000,
                end_ms=turn.end * 1000,
                speaker_id=speaker,
                duration_ms=(turn.end - turn.start) * 1000
            ))
        
        # 4. 清理临时文件
        os.remove(temp_path)
        
        return DiarizationResult(
            segments=segments,
            num_speakers=len(set(seg.speaker_id for seg in segments))
        )
    
    async def diarize_and_transcribe(
        self,
        audio_data: bytes,
        language: str = "zh"
    ) -> TranscriptWithSpeakers:
        """说话人分离 + 语音识别"""
        
        # 1. 说话人分离
        diarization_result = await self.diarize(audio_data)
        
        # 2. 为每个片段识别
        transcripts = []
        for segment in diarization_result.segments:
            # 提取片段音频
            segment_audio = self._extract_audio_segment(
                audio_data,
                segment.start_ms,
                segment.end_ms
            )
            
            # ASR识别
            asr_result = await self.asr_service.recognize_from_bytes(
                segment_audio,
                language=language
            )
            
            transcripts.append(SpeakerTranscript(
                speaker_id=segment.speaker_id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=asr_result.text,
                confidence=asr_result.confidence
            ))
        
        return TranscriptWithSpeakers(
            transcripts=transcripts,
            num_speakers=diarization_result.num_speakers
        )
```

#### Sprint 2: 情感识别（1周）

**目标**: 识别语音情感（愤怒、悲伤、高兴等）

```python
# File: app/services/emotion_recognition_service.py

import librosa
import numpy as np
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor

class EmotionRecognitionService:
    """情感识别服务"""
    
    def __init__(self):
        # 加载预训练的情感识别模型
        self.processor = Wav2Vec2Processor.from_pretrained(
            "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
        )
        self.model = Wav2Vec2ForSequenceClassification.from_pretrained(
            "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
        )
        
        self.emotions = ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]
    
    async def recognize_emotion(
        self,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> EmotionResult:
        """识别语音情感"""
        
        # 1. 加载音频
        audio, sr = librosa.load(
            io.BytesIO(audio_data),
            sr=sample_rate
        )
        
        # 2. 预处理
        inputs = self.processor(
            audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True
        )
        
        # 3. 模型推理
        with torch.no_grad():
            logits = self.model(**inputs).logits
            predictions = torch.nn.functional.softmax(logits, dim=-1)
        
        # 4. 解析结果
        emotion_scores = {}
        for i, emotion in enumerate(self.emotions):
            emotion_scores[emotion] = float(predictions[0][i])
        
        # 获取主要情感
        primary_emotion = max(emotion_scores.items(), key=lambda x: x[1])
        
        return EmotionResult(
            primary_emotion=primary_emotion[0],
            confidence=primary_emotion[1],
            all_emotions=emotion_scores
        )
```

#### Sprint 3: 噪音抑制（1周）

**目标**: 实时音频降噪

```python
# File: app/services/noise_suppression_service.py

import noisereduce as nr
import soundfile as sf

class NoiseSuppressionService:
    """噪音抑制服务"""
    
    async def reduce_noise(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        stationary: bool = True
    ) -> bytes:
        """降噪处理"""
        
        # 1. 加载音频
        audio, sr = librosa.load(
            io.BytesIO(audio_data),
            sr=sample_rate
        )
        
        # 2. 降噪
        if stationary:
            # 平稳噪音（如风扇、空调）
            reduced_audio = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=True,
                prop_decrease=1.0
            )
        else:
            # 非平稳噪音（如突发声音）
            reduced_audio = nr.reduce_noise(
                y=audio,
                sr=sr,
                stationary=False,
                use_torch=True
            )
        
        # 3. 转换回bytes
        output_buffer = io.BytesIO()
        sf.write(output_buffer, reduced_audio, sr, format='WAV')
        output_buffer.seek(0)
        
        return output_buffer.read()
```

### 2.3 API接口示例

```python
# File: app/routers/voice_advanced.py

from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api/v1/voice/advanced", tags=["Voice Advanced"])

@router.post("/diarize", response_model=DiarizationResult)
async def diarize_audio(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = None
):
    """说话人分离"""
    audio_data = await file.read()
    return await speaker_diarization_service.diarize(
        audio_data,
        num_speakers=num_speakers
    )

@router.post("/diarize-and-transcribe", response_model=TranscriptWithSpeakers)
async def diarize_and_transcribe(
    file: UploadFile = File(...),
    language: str = "zh"
):
    """说话人分离 + 语音识别"""
    audio_data = await file.read()
    return await speaker_diarization_service.diarize_and_transcribe(
        audio_data,
        language=language
    )

@router.post("/emotion", response_model=EmotionResult)
async def recognize_emotion(
    file: UploadFile = File(...)
):
    """情感识别"""
    audio_data = await file.read()
    return await emotion_recognition_service.recognize_emotion(audio_data)

@router.post("/denoise", response_model=AudioResponse)
async def reduce_noise(
    file: UploadFile = File(...),
    stationary: bool = True
):
    """降噪处理"""
    audio_data = await file.read()
    reduced_audio = await noise_suppression_service.reduce_noise(
        audio_data,
        stationary=stationary
    )
    
    return AudioResponse(
        audio_base64=base64.b64encode(reduced_audio).decode(),
        sample_rate=16000
    )
```

### 2.4 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| ASR延迟 | ~500ms | < 300ms | P95 < 500ms |
| TTS延迟 | ~800ms | < 500ms | P95 < 1s |
| 说话人分离准确率 | N/A | > 85% | F1 > 0.85 |
| 情感识别准确率 | N/A | > 70% | Top-1 > 70% |

---

## 3. RAG Engine

### 3.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| 完整RAG流程 | ✅ 完成 | 检索→重排→生成 |
| 查询理解 | ✅ 完成 | 查询扩展、关键词提取 |
| 检索增强 | ✅ 完成 | 多查询融合、去重排序 |
| 上下文管理 | ✅ 完成 | 智能组装、长度控制 |
| 生成服务 | ✅ 完成 | 流式响应支持 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | Cross-Encoder重排序 | 部分实现 | 2天 |
| P0 | 语义缓存 | 未实现 | 3天 |
| P1 | 自适应检索 | 未实现 | 4天 |
| P1 | 混合检索（BM25+向量） | 未实现 | 3天 |
| P2 | 多轮对话上下文 | 未实现 | 5天 |
| P2 | 答案后处理 | 未实现 | 2天 |

### 3.2 迭代计划

#### Sprint 1: Cross-Encoder重排序和语义缓存（1周）

**目标**: 完善重排序，实现语义缓存

**1. Cross-Encoder重排序**

```python
# File: app/services/rerank_service.py

from sentence_transformers import CrossEncoder

class RerankService:
    """重排序服务"""
    
    def __init__(self):
        # 加载Cross-Encoder模型
        self.cross_encoder = CrossEncoder(
            'cross-encoder/ms-marco-MiniLM-L-12-v2',
            max_length=512
        )
    
    async def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: int = 10
    ) -> List[RetrievedDocument]:
        """使用Cross-Encoder重排序"""
        
        # 1. 构建query-document对
        pairs = [(query, doc.content) for doc in documents]
        
        # 2. 计算相关性分数
        scores = self.cross_encoder.predict(pairs)
        
        # 3. 按分数排序
        for doc, score in zip(documents, scores):
            doc.rerank_score = float(score)
        
        documents_sorted = sorted(
            documents,
            key=lambda x: x.rerank_score,
            reverse=True
        )
        
        return documents_sorted[:top_k]
```

**2. 语义缓存**

```python
# File: app/services/semantic_cache_service.py

import redis
from sentence_transformers import SentenceTransformer

class SemanticCacheService:
    """语义缓存服务"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.similarity_threshold = 0.9  # 相似度阈值
    
    async def get_cached_answer(
        self,
        query: str
    ) -> Optional[CachedAnswer]:
        """获取缓存的答案"""
        
        # 1. 查询embedding
        query_embedding = self.embedding_model.encode(query)
        
        # 2. 从Redis获取所有缓存的查询
        cached_queries = self._get_all_cached_queries()
        
        # 3. 计算相似度
        for cached_query in cached_queries:
            similarity = self._cosine_similarity(
                query_embedding,
                cached_query.embedding
            )
            
            if similarity >= self.similarity_threshold:
                # 命中缓存
                cached_answer = self.redis_client.get(
                    f"semantic_cache:{cached_query.id}"
                )
                return CachedAnswer(
                    answer=cached_answer,
                    similarity=similarity,
                    original_query=cached_query.query
                )
        
        return None
    
    async def set_cached_answer(
        self,
        query: str,
        answer: str,
        ttl: int = 3600
    ):
        """设置缓存答案"""
        
        # 1. 计算query embedding
        query_embedding = self.embedding_model.encode(query)
        
        # 2. 生成缓存ID
        cache_id = hashlib.md5(query.encode()).hexdigest()
        
        # 3. 保存到Redis
        self.redis_client.setex(
            f"semantic_cache:{cache_id}",
            ttl,
            answer
        )
        
        # 4. 保存query和embedding
        self.redis_client.setex(
            f"semantic_cache:query:{cache_id}",
            ttl,
            json.dumps({
                "query": query,
                "embedding": query_embedding.tolist()
            })
        )
```

**集成到RAG流程**:

```python
# File: app/services/rag_service.py

class RAGService:
    async def generate(
        self,
        request: RAGRequest
    ) -> RAGResponse:
        """RAG生成（带语义缓存）"""
        
        # 1. 检查语义缓存
        cached_answer = await self.semantic_cache.get_cached_answer(request.query)
        if cached_answer:
            return RAGResponse(
                query=request.query,
                answer=cached_answer.answer,
                sources=[],
                from_cache=True,
                cache_similarity=cached_answer.similarity
            )
        
        # 2. 查询扩展
        if request.enable_query_expansion:
            expanded_queries = await self.query_service.expand_query(
                request.query,
                num_expansions=2
            )
        else:
            expanded_queries = [request.query]
        
        # 3. 检索
        all_documents = []
        for query in expanded_queries:
            docs = await self.retrieval_client.search(
                query=query,
                tenant_id=request.tenant_id,
                knowledge_base_id=request.knowledge_base_id,
                top_k=request.top_k
            )
            all_documents.extend(docs)
        
        # 4. 去重和排序
        unique_documents = self._deduplicate(all_documents)
        
        # 5. 重排序
        if request.enable_rerank:
            reranked_documents = await self.rerank_service.rerank(
                query=request.query,
                documents=unique_documents,
                top_k=request.rerank_top_k
            )
        else:
            reranked_documents = unique_documents[:request.top_k]
        
        # 6. 构建上下文
        context = await self.context_service.build_context(
            documents=reranked_documents,
            max_length=4000
        )
        
        # 7. 生成答案
        answer = await self.generator_service.generate(
            query=request.query,
            context=context,
            history=request.history,
            model=request.model
        )
        
        # 8. 缓存答案
        await self.semantic_cache.set_cached_answer(
            query=request.query,
            answer=answer,
            ttl=3600
        )
        
        return RAGResponse(
            query=request.query,
            answer=answer,
            sources=reranked_documents,
            from_cache=False
        )
```

#### Sprint 2: 自适应检索和混合检索（1周）

**目标**: 根据查询难度自适应调整检索策略，实现混合检索

```python
# File: app/services/adaptive_retrieval_service.py

class AdaptiveRetrievalService:
    """自适应检索服务"""
    
    async def adaptive_search(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: str
    ) -> List[RetrievedDocument]:
        """自适应检索"""
        
        # 1. 分析查询复杂度
        complexity = await self._analyze_query_complexity(query)
        
        # 2. 根据复杂度选择策略
        if complexity.level == "simple":
            # 简单查询：仅向量检索，top 5
            documents = await self.vector_search(query, top_k=5)
        
        elif complexity.level == "medium":
            # 中等查询：混合检索，top 10
            documents = await self.hybrid_search(query, top_k=10)
        
        else:  # complex
            # 复杂查询：混合检索 + 查询扩展 + 重排序，top 20
            expanded_queries = await self.expand_query(query)
            all_docs = []
            for q in expanded_queries:
                docs = await self.hybrid_search(q, top_k=10)
                all_docs.extend(docs)
            
            # 去重
            unique_docs = self._deduplicate(all_docs)
            
            # 重排序
            documents = await self.rerank(query, unique_docs, top_k=20)
        
        return documents
    
    async def _analyze_query_complexity(
        self,
        query: str
    ) -> QueryComplexity:
        """分析查询复杂度"""
        
        # 启发式规则
        factors = {
            "length": len(query.split()),
            "has_numbers": bool(re.search(r'\d', query)),
            "has_comparison": any(w in query for w in ["比较", "对比", "区别"]),
            "has_aggregation": any(w in query for w in ["总结", "汇总", "统计"]),
            "has_temporal": any(w in query for w in ["最近", "最新", "历史"])
        }
        
        # 计算复杂度分数
        score = 0
        if factors["length"] > 20:
            score += 2
        if factors["has_comparison"]:
            score += 2
        if factors["has_aggregation"]:
            score += 3
        if factors["has_temporal"]:
            score += 1
        
        # 判断级别
        if score <= 2:
            level = "simple"
        elif score <= 5:
            level = "medium"
        else:
            level = "complex"
        
        return QueryComplexity(level=level, score=score, factors=factors)
```

**混合检索实现**:

```python
# File: app/services/hybrid_search_service.py

class HybridSearchService:
    """混合检索服务（向量 + BM25）"""
    
    async def hybrid_search(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: str,
        top_k: int = 10,
        alpha: float = 0.5  # 向量权重
    ) -> List[RetrievedDocument]:
        """混合检索"""
        
        # 1. 并行执行向量检索和BM25检索
        vector_task = self._vector_search(query, top_k=top_k * 2)
        bm25_task = self._bm25_search(query, top_k=top_k * 2)
        
        vector_docs, bm25_docs = await asyncio.gather(vector_task, bm25_task)
        
        # 2. 归一化分数
        vector_docs = self._normalize_scores(vector_docs)
        bm25_docs = self._normalize_scores(bm25_docs)
        
        # 3. 融合分数
        doc_scores = {}
        for doc in vector_docs:
            doc_scores[doc.chunk_id] = {
                "doc": doc,
                "vector_score": doc.score,
                "bm25_score": 0.0
            }
        
        for doc in bm25_docs:
            if doc.chunk_id in doc_scores:
                doc_scores[doc.chunk_id]["bm25_score"] = doc.score
            else:
                doc_scores[doc.chunk_id] = {
                    "doc": doc,
                    "vector_score": 0.0,
                    "bm25_score": doc.score
                }
        
        # 4. 计算混合分数
        for chunk_id, scores in doc_scores.items():
            hybrid_score = (
                alpha * scores["vector_score"] +
                (1 - alpha) * scores["bm25_score"]
            )
            scores["doc"].score = hybrid_score
        
        # 5. 按混合分数排序
        hybrid_docs = [s["doc"] for s in doc_scores.values()]
        hybrid_docs_sorted = sorted(
            hybrid_docs,
            key=lambda x: x.score,
            reverse=True
        )
        
        return hybrid_docs_sorted[:top_k]
```

### 3.3 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| 端到端延迟 | ~2.5s | < 2s | P95 < 3s |
| 检索召回率 | 90% | > 95% | MRR > 0.9 |
| 答案准确率 | 85% | > 90% | F1 > 0.9 |
| 缓存命中率 | 0% | > 30% | 减少30%请求 |

---

## 4. Retrieval Service

### 4.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| 向量检索 | ✅ 完成 | Milvus HNSW索引 |
| BM25检索 | ✅ 完成 | Elasticsearch全文检索 |
| RRF融合 | ✅ 完成 | Reciprocal Rank Fusion |
| Cross-Encoder重排 | ✅ 完成 | MiniLM-L-12-v2 |
| 多租户隔离 | ✅ 完成 | tenant_id过滤 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | 集成Embedding服务 | 未实现 | 2天 |
| P1 | 查询改写 | 未实现 | 3天 |
| P1 | 个性化检索 | 未实现 | 5天 |
| P2 | 多模态检索 | 未实现 | 7天 |

### 4.2 迭代计划

#### Sprint 1: 集成Embedding服务（1周）

**目标**: 自动获取查询向量，无需调用方提供

```python
# File: app/services/embedding_service.py

from sentence_transformers import SentenceTransformer

class EmbeddingService:
    """Embedding服务"""
    
    def __init__(self):
        # 加载BGE-M3模型（中文优化）
        self.model = SentenceTransformer('BAAI/bge-m3')
    
    async def embed_query(
        self,
        query: str
    ) -> List[float]:
        """查询向量化"""
        
        # 添加查询指令
        query_with_instruction = f"Represent this sentence for searching relevant passages: {query}"
        
        embedding = self.model.encode(
            query_with_instruction,
            normalize_embeddings=True
        )
        
        return embedding.tolist()
    
    async def embed_batch(
        self,
        texts: List[str],
        is_query: bool = False
    ) -> List[List[float]]:
        """批量向量化"""
        
        if is_query:
            texts = [f"Represent this sentence for searching relevant passages: {t}" for t in texts]
        
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32
        )
        
        return embeddings.tolist()

# 集成到检索服务
class RetrievalService:
    async def vector_search(
        self,
        request: VectorSearchRequest
    ) -> List[RetrievedDocument]:
        """向量检索（自动Embedding）"""
        
        # 1. 如果没有提供embedding，自动生成
        if request.query_embedding is None:
            query_embedding = await self.embedding_service.embed_query(request.query)
        else:
            query_embedding = request.query_embedding
        
        # 2. 调用Milvus检索
        documents = await self.vector_service.search(
            collection_name=request.collection_name,
            query_vector=query_embedding,
            top_k=request.top_k,
            filters=request.filters
        )
        
        return documents
```

#### Sprint 2: 查询改写（1周）

**目标**: 自动优化查询，提升检索效果

```python
# File: app/services/query_rewriter_service.py

class QueryRewriterService:
    """查询改写服务"""
    
    async def rewrite_query(
        self,
        query: str,
        context: Optional[List[str]] = None
    ) -> RewrittenQuery:
        """查询改写"""
        
        # 构建改写提示词
        prompt = self._build_rewrite_prompt(query, context)
        
        # 调用LLM改写
        response = await self.llm_service.chat(
            messages=[
                {"role": "system", "content": "You are a query rewriter that improves search queries."},
                {"role": "user", "content": prompt}
            ],
            model="gpt-3.5-turbo",
            temperature=0.3
        )
        
        rewritten = response["choices"][0]["message"]["content"]
        
        return RewrittenQuery(
            original=query,
            rewritten=rewritten
        )
    
    def _build_rewrite_prompt(
        self,
        query: str,
        context: Optional[List[str]]
    ) -> str:
        """构建改写提示词"""
        
        prompt = f"""请改写以下查询，使其更适合语义检索：

原始查询: {query}
"""
        
        if context:
            prompt += f"\n对话上下文:\n" + "\n".join(context)
        
        prompt += """

改写要求：
1. 补全缺失的主语或宾语
2. 将口语化表达转为书面语
3. 明确查询意图
4. 保留关键信息

改写后的查询："""
        
        return prompt
```

---

## 5. Model Adapter

### 5.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| 多提供商支持 | ✅ 完成 | OpenAI、Anthropic、Azure等 |
| 统一接口 | ✅ 完成 | Chat、Completion、Embedding |
| 自动路由 | ✅ 完成 | 根据模型名称选择提供商 |
| 流式支持 | ✅ 完成 | SSE流式响应 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | 国产模型完善 | 部分实现 | 3天 |
| P0 | 请求缓存 | 未实现 | 2天 |
| P1 | 重试机制 | 未实现 | 2天 |
| P1 | 智能降级 | 未实现 | 3天 |
| P2 | 成本优化路由 | 未实现 | 4天 |

### 5.2 迭代计划

#### Sprint 1: 国产模型完善和请求缓存（1周）

**1. 智谱AI适配器完善**

```python
# File: app/adapters/zhipu_adapter.py

class ZhipuAdapter(BaseAdapter):
    """智谱AI适配器"""
    
    async def chat(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """智谱GLM-4聊天"""
        
        # 1. 转换消息格式
        zhipu_messages = self._convert_messages(request.messages)
        
        # 2. 构建请求
        payload = {
            "model": request.model,
            "messages": zhipu_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream
        }
        
        # 3. 调用智谱API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.ZHIPU_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
        
        # 4. 转换为统一格式
        return ChatResponse(
            id=result["id"],
            model=result["model"],
            provider="zhipu",
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=result["choices"][0]["message"]["content"]
                    ),
                    finish_reason=result["choices"][0]["finish_reason"]
                )
            ],
            usage=Usage(
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
                total_tokens=result["usage"]["total_tokens"]
            )
        )
```

**2. 请求缓存实现**

```python
# File: app/services/cache_service.py

import hashlib
import json

class RequestCacheService:
    """请求缓存服务"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT
        )
    
    def _generate_cache_key(
        self,
        request: ChatRequest
    ) -> str:
        """生成缓存键"""
        
        # 序列化请求
        request_dict = {
            "model": request.model,
            "messages": [m.dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        request_str = json.dumps(request_dict, sort_keys=True)
        
        # 生成哈希
        return f"model_adapter:cache:{hashlib.sha256(request_str.encode()).hexdigest()}"
    
    async def get_cached_response(
        self,
        request: ChatRequest
    ) -> Optional[ChatResponse]:
        """获取缓存的响应"""
        
        # 1. 生成缓存键
        cache_key = self._generate_cache_key(request)
        
        # 2. 从Redis获取
        cached_data = self.redis_client.get(cache_key)
        if cached_data:
            return ChatResponse.parse_raw(cached_data)
        
        return None
    
    async def set_cached_response(
        self,
        request: ChatRequest,
        response: ChatResponse,
        ttl: int = 3600
    ):
        """设置缓存响应"""
        
        cache_key = self._generate_cache_key(request)
        self.redis_client.setex(
            cache_key,
            ttl,
            response.json()
        )
```

### 5.3 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| 平均响应时间 | ~1.5s | < 1.2s | P95 < 2s |
| 缓存命中率 | 0% | > 40% | 减少40%请求 |
| 错误率 | < 1% | < 0.5% | 可用性99.5% |

---

## 6-9. 其他服务简要计划

### 6. Indexing Service

**P0任务**:
- 完善PDF表格和图片解析
- 实现智能分块策略
- 添加向量缓存

**P1任务**:
- 支持更多文档格式（PPT、Excel）
- 实体识别和知识图谱增强
- 增量索引

### 7. Multimodal Engine

**P0任务**:
- EasyOCR集成
- 批量OCR处理
- 结果缓存

**P1任务**:
- 专用目标检测（YOLO）
- 图像分割
- 批量处理

### 8. Vector Store Adapter

**P0任务**:
- 添加缓存层（Redis）
- 批量操作优化
- 重试机制

**P1任务**:
- 添加更多后端（Qdrant, Weaviate）
- 流式插入支持
- 自动分片和负载均衡

### 9. Knowledge Service (Python)

**P0任务**:
- Proto定义完善
- 集成文件解析器
- 实现智能分块

**P1任务**:
- 集成向量化服务
- 添加pgvector支持
- 文档摘要生成

---

## 总体时间线

### Phase 1: 核心功能完善（1-2个月）

**Week 1-2**: Agent Engine流式响应 + Voice Engine说话人分离
**Week 3-4**: RAG Engine重排序和缓存 + Retrieval Service集成
**Week 5-6**: Model Adapter国产模型 + Indexing Service PDF解析
**Week 7-8**: Multimodal Engine目标检测 + Vector Store Adapter优化

### Phase 2: 高级功能开发（2-3个月）

**Week 9-12**: 多Agent协作 + 情感识别 + 自适应检索
**Week 13-16**: 人工反馈循环 + 个性化检索 + 智能降级

### Phase 3: 性能优化和测试（1个月）

**Week 17-20**: 性能测试、压力测试、优化调优

---

## 验收标准

### 功能验收

- ✅ 所有P0功能实现并测试通过
- ✅ 所有P1功能至少完成80%
- ✅ API文档完整
- ✅ 单元测试覆盖率 > 80%

### 性能验收

- ✅ 满足所有性能指标目标值
- ✅ 并发压力测试通过
- ✅ 内存和CPU使用在合理范围

### 质量验收

- ✅ 代码审查通过
- ✅ 安全扫描无高危漏洞
- ✅ 监控和告警配置完整

---

**文档版本**: v2.0  
**最后更新**: 2025-10-27  
**维护者**: VoiceHelper Team


