# VoiceAssistant 功能迁移迭代计划 v2.0

> **生成时间**: 2025-10-27
> **基于**: voicehelper v0.9.2 功能对比分析
> **当前版本**: VoiceAssistant v2.0.0
> **目标版本**: v2.3.0
> **预计周期**: 10 周 (2.5 个月)

---

## 📊 执行摘要

本迭代计划基于对 [voicehelper](https://github.com/haoyunlt/voicehelper) 项目的深度分析，识别出 **15 项**值得迁移的功能特性，按优先级分为 P0/P1/P2 三个等级，规划为 **3 个版本**（v2.1.0/v2.2.0/v2.3.0）逐步交付。

### 核心目标

- ✅ 提升系统稳定性和可靠性
- ✅ 增强 AI 核心能力（语音、记忆、模型）
- ✅ 完善移动端支持
- ✅ 优化开发者体验

### 总体进度

```
总工时预估: 120-150 人天
当前状态:  准备启动
完成度:    [░░░░░░░░░░░░░░░░░░░░] 0%
```

---

## 🎯 版本规划总览

| 版本   | 主题     | 时间线    | 功能数 | 优先级 | 状态      |
| ------ | -------- | --------- | ------ | ------ | --------- |
| v2.1.0 | 核心增强 | Week 1-3  | 7 项   | P0     | 📋 规划中 |
| v2.2.0 | 功能扩展 | Week 4-7  | 5 项   | P1     | 📋 规划中 |
| v2.3.0 | 优化提升 | Week 8-10 | 3 项   | P2     | 📋 规划中 |

---

## 📦 v2.1.0 核心增强 (Week 1-3)

**发布目标日期**: 3 周后
**核心价值**: 提升系统稳定性、AI 能力和安全性

### Sprint 1: 系统可靠性 (Week 1)

#### 🎯 Sprint 目标

- 提升 Agent 任务管理的可靠性
- 实现全局分布式限流
- 增强 Agent 长期记忆能力

#### 📋 任务清单

##### 1. 任务状态 Redis 持久化

**负责人**: Backend Team
**预估工时**: 2-3 天
**优先级**: P0

**详细说明**:

- 当前 Agent Engine 的任务状态存储在内存中，服务重启后任务丢失
- voicehelper 使用 Redis 持久化任务状态，提供更好的可靠性

**实现要点**:

```python
# algo/agent-engine/app/core/task_manager.py

class RedisTaskManager:
    """Redis 持久化任务管理器"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.task_prefix = "agent:task:"
        self.task_index = "agent:tasks:index"

    async def create_task(self, task: AgentTask) -> str:
        """创建任务并持久化"""
        task_id = str(uuid.uuid4())
        task_key = f"{self.task_prefix}{task_id}"

        # 保存任务数据
        await self.redis.hset(task_key, mapping={
            "id": task_id,
            "user_id": task.user_id,
            "tenant_id": task.tenant_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "payload": json.dumps(task.dict())
        })

        # 添加到索引（按用户）
        await self.redis.sadd(
            f"{self.task_index}:user:{task.user_id}",
            task_id
        )

        # 设置过期时间（7天）
        await self.redis.expire(task_key, 7 * 24 * 3600)

        return task_id

    async def update_task_status(self, task_id: str, status: str, result: dict = None):
        """更新任务状态"""
        task_key = f"{self.task_prefix}{task_id}"

        updates = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        if result:
            updates["result"] = json.dumps(result)

        await self.redis.hset(task_key, mapping=updates)

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务"""
        task_key = f"{self.task_prefix}{task_id}"
        data = await self.redis.hgetall(task_key)

        if not data:
            return None

        return AgentTask.parse_obj(json.loads(data["payload"]))

    async def list_user_tasks(self, user_id: str, status: str = None) -> List[AgentTask]:
        """查询用户任务列表"""
        task_ids = await self.redis.smembers(f"{self.task_index}:user:{user_id}")

        tasks = []
        for task_id in task_ids:
            task = await self.get_task(task_id)
            if task and (status is None or task.status == status):
                tasks.append(task)

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
```

**API 接口**:

```python
# algo/agent-engine/app/api/task_routes.py

@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest, task_manager: RedisTaskManager = Depends()):
    """创建 Agent 任务"""
    task_id = await task_manager.create_task(request.task)
    return TaskResponse(task_id=task_id, status="pending")

@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str, task_manager: RedisTaskManager = Depends()):
    """查询任务详情"""
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks", response_model=List[TaskSummary])
async def list_tasks(
    user_id: str = Query(...),
    status: Optional[str] = Query(None),
    task_manager: RedisTaskManager = Depends()
):
    """查询用户任务列表"""
    tasks = await task_manager.list_user_tasks(user_id, status)
    return [TaskSummary.from_task(t) for t in tasks]
```

**测试要求**:

- 单元测试: 任务 CRUD 操作
- 集成测试: Redis 连接失败降级
- 性能测试: 1000 并发任务创建
- 可靠性测试: 服务重启后任务恢复

**验收标准**:

- [ ] 任务创建后写入 Redis
- [ ] 服务重启后任务状态不丢失
- [ ] 支持按用户、状态查询任务
- [ ] 任务自动过期（7 天）
- [ ] 单元测试覆盖率 > 80%
- [ ] API 文档更新

---

##### 2. 分布式限流器 (Redis)

**负责人**: Backend Team
**预估工时**: 3-4 天
**优先级**: P0

**详细说明**:

- 当前 API Gateway 使用本地内存限流，多实例环境下无法全局限流
- voicehelper 使用 Redis 实现分布式限流，支持全局流量控制

**实现要点**:

```go
// pkg/middleware/rate_limiter.go

package middleware

import (
    "context"
    "fmt"
    "time"

    "github.com/go-redis/redis/v8"
    "github.com/go-kratos/kratos/v2/errors"
    "github.com/go-kratos/kratos/v2/middleware"
    "github.com/go-kratos/kratos/v2/transport"
)

// RateLimiterConfig 限流配置
type RateLimiterConfig struct {
    // 每秒请求数
    RequestsPerSecond int
    // 突发容量
    Burst int
    // Redis 客户端
    Redis *redis.Client
    // 限流维度提取函数
    KeyExtractor func(ctx context.Context) (string, error)
}

// RateLimiter 分布式限流中间件
func RateLimiter(config *RateLimiterConfig) middleware.Middleware {
    return func(handler middleware.Handler) middleware.Handler {
        return func(ctx context.Context, req interface{}) (interface{}, error) {
            // 提取限流 Key (user_id, tenant_id, ip, api_key 等)
            key, err := config.KeyExtractor(ctx)
            if err != nil {
                return nil, err
            }

            // 令牌桶算法 (Token Bucket)
            allowed, err := checkRateLimit(ctx, config.Redis, key, config.RequestsPerSecond, config.Burst)
            if err != nil {
                return nil, errors.InternalServer("RATE_LIMIT_ERROR", err.Error())
            }

            if !allowed {
                return nil, errors.TooManyRequests("RATE_LIMIT_EXCEEDED", "Too many requests, please try again later")
            }

            return handler(ctx, req)
        }
    }
}

// checkRateLimit 使用 Redis 实现令牌桶算法
func checkRateLimit(ctx context.Context, rdb *redis.Client, key string, rate int, burst int) (bool, error) {
    luaScript := `
local key = KEYS[1]
local rate = tonumber(ARGV[1])    -- 每秒生成 token 数
local burst = tonumber(ARGV[2])   -- 桶容量
local now = tonumber(ARGV[3])     -- 当前时间戳（毫秒）
local requested = 1               -- 本次请求消耗 1 token

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or burst
local last_refill = tonumber(bucket[2]) or now

-- 计算距离上次补充的时间间隔
local delta = math.max(0, now - last_refill)
-- 计算应补充的 token 数量
local refill = (delta / 1000) * rate
tokens = math.min(burst, tokens + refill)

-- 检查是否有足够的 token
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 60)  -- 设置过期时间
    return 1  -- 允许通过
else
    return 0  -- 限流
end
`

    now := time.Now().UnixNano() / 1e6 // 毫秒
    result, err := rdb.Eval(ctx, luaScript, []string{fmt.Sprintf("ratelimit:%s", key)}, rate, burst, now).Result()
    if err != nil {
        return false, err
    }

    return result.(int64) == 1, nil
}

// 内置 Key 提取器

// ByUserID 按用户 ID 限流
func ByUserID(ctx context.Context) (string, error) {
    if tr, ok := transport.FromServerContext(ctx); ok {
        userID := tr.RequestHeader().Get("X-User-ID")
        if userID != "" {
            return fmt.Sprintf("user:%s", userID), nil
        }
    }
    return "", errors.BadRequest("MISSING_USER_ID", "User ID not found in context")
}

// ByTenantID 按租户 ID 限流
func ByTenantID(ctx context.Context) (string, error) {
    if tr, ok := transport.FromServerContext(ctx); ok {
        tenantID := tr.RequestHeader().Get("X-Tenant-ID")
        if tenantID != "" {
            return fmt.Sprintf("tenant:%s", tenantID), nil
        }
    }
    return "", errors.BadRequest("MISSING_TENANT_ID", "Tenant ID not found in context")
}

// ByIP 按 IP 地址限流
func ByIP(ctx context.Context) (string, error) {
    if tr, ok := transport.FromServerContext(ctx); ok {
        ip := tr.RequestHeader().Get("X-Forwarded-For")
        if ip == "" {
            ip = tr.RequestHeader().Get("X-Real-IP")
        }
        if ip != "" {
            return fmt.Sprintf("ip:%s", ip), nil
        }
    }
    return "", errors.BadRequest("MISSING_IP", "IP address not found in context")
}
```

**使用示例**:

```go
// cmd/ai-orchestrator/internal/server/grpc.go

import (
    "voicehelper/pkg/middleware"
)

func NewGRPCServer(c *conf.Server, redis *redis.Client) *grpc.Server {
    var opts = []grpc.ServerOption{
        grpc.Middleware(
            // 用户级别限流: 100 req/s, burst 50
            middleware.RateLimiter(&middleware.RateLimiterConfig{
                RequestsPerSecond: 100,
                Burst:             50,
                Redis:             redis,
                KeyExtractor:      middleware.ByUserID,
            }),
            // 租户级别限流: 10000 req/s, burst 1000
            middleware.RateLimiter(&middleware.RateLimiterConfig{
                RequestsPerSecond: 10000,
                Burst:             1000,
                Redis:             redis,
                KeyExtractor:      middleware.ByTenantID,
            }),
        ),
    }
    srv := grpc.NewServer(opts...)
    return srv
}
```

**测试要求**:

- 单元测试: Lua 脚本逻辑
- 集成测试: 多实例限流一致性
- 压力测试: 并发请求限流准确性
- 故障测试: Redis 不可用时降级

**验收标准**:

- [ ] 令牌桶算法正确实现
- [ ] 多实例环境全局限流生效
- [ ] 支持用户/租户/IP 多维度限流
- [ ] Redis 故障时优雅降级（放行或拒绝）
- [ ] 限流响应包含 `X-RateLimit-*` Headers
- [ ] 性能开销 < 5ms (P95)

---

##### 3. 长期记忆时间衰减机制

**负责人**: AI Team
**预估工时**: 2 天
**优先级**: P0

**详细说明**:

- 当前 Agent 长期记忆评分固定，不符合人类记忆遗忘规律
- voicehelper 实现时间衰减机制，记忆重要性随时间递减

**实现要点**:

```python
# algo/agent-engine/app/core/memory/decay_manager.py

import math
from datetime import datetime, timedelta
from typing import List, Optional

class MemoryDecayManager:
    """记忆衰减管理器

    基于 Ebbinghaus 遗忘曲线实现记忆衰减:
    R(t) = e^(-t/S)

    其中:
    - R(t): t 时刻的记忆强度
    - t: 距离创建时间的天数
    - S: 记忆稳定性参数 (默认 7 天)
    """

    def __init__(self, stability_days: float = 7.0):
        self.stability_days = stability_days

    def calculate_decay_score(
        self,
        created_at: datetime,
        importance: float = 1.0,
        access_count: int = 0,
        last_accessed: Optional[datetime] = None
    ) -> float:
        """计算衰减后的记忆分数

        Args:
            created_at: 记忆创建时间
            importance: 初始重要性 (0.0-1.0)
            access_count: 访问次数
            last_accessed: 最后访问时间

        Returns:
            衰减后的分数 (0.0-1.0)
        """
        # 1. 基础衰减（Ebbinghaus 曲线）
        days_passed = (datetime.utcnow() - created_at).total_seconds() / 86400
        base_decay = math.exp(-days_passed / self.stability_days)

        # 2. 重访增强（每次访问延长记忆寿命）
        access_boost = 1.0 + (access_count * 0.1)  # 每访问一次 +10%
        access_boost = min(access_boost, 3.0)  # 最多 3 倍

        # 3. 近期访问增强
        recency_boost = 1.0
        if last_accessed:
            days_since_access = (datetime.utcnow() - last_accessed).total_seconds() / 86400
            recency_boost = 1.0 + math.exp(-days_since_access / 3.0)

        # 综合分数
        final_score = importance * base_decay * access_boost * recency_boost

        return min(final_score, 1.0)

    def should_forget(self, score: float, threshold: float = 0.1) -> bool:
        """判断是否应该遗忘"""
        return score < threshold

    def get_retention_days(self, importance: float) -> int:
        """计算记忆保留天数"""
        # 重要性越高，保留越久
        if importance >= 0.9:
            return 365  # 1 年
        elif importance >= 0.7:
            return 90   # 3 个月
        elif importance >= 0.5:
            return 30   # 1 个月
        else:
            return 7    # 1 周

# 集成到 VectorMemory

class VectorMemory:
    """向量记忆存储（集成衰减机制）"""

    def __init__(self, faiss_index, metadata_store, decay_manager: MemoryDecayManager):
        self.index = faiss_index
        self.metadata = metadata_store
        self.decay_manager = decay_manager

    async def add_memory(
        self,
        content: str,
        embedding: np.ndarray,
        importance: float = 0.5,
        metadata: dict = None
    ) -> str:
        """添加记忆"""
        memory_id = str(uuid.uuid4())

        # 存储向量
        self.index.add(embedding)

        # 存储元数据
        memory_metadata = {
            "id": memory_id,
            "content": content,
            "importance": importance,
            "created_at": datetime.utcnow().isoformat(),
            "access_count": 0,
            "last_accessed": None,
            "metadata": metadata or {}
        }
        await self.metadata.set(f"memory:{memory_id}", json.dumps(memory_metadata))

        return memory_id

    async def recall_memory(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_score: float = 0.1
    ) -> List[Memory]:
        """召回记忆（考虑衰减）"""
        # 1. 向量检索（召回 top_k * 3，后续过滤）
        distances, indices = self.index.search(query_embedding, top_k * 3)

        # 2. 加载元数据并计算衰减分数
        memories = []
        for idx, distance in zip(indices[0], distances[0]):
            memory_data = await self.metadata.get(f"memory:{idx}")
            if not memory_data:
                continue

            meta = json.loads(memory_data)

            # 计算衰减后的分数
            decay_score = self.decay_manager.calculate_decay_score(
                created_at=datetime.fromisoformat(meta["created_at"]),
                importance=meta["importance"],
                access_count=meta["access_count"],
                last_accessed=datetime.fromisoformat(meta["last_accessed"]) if meta["last_accessed"] else None
            )

            # 综合相似度和衰减分数
            final_score = distance * decay_score

            if final_score >= min_score:
                memories.append(Memory(
                    id=meta["id"],
                    content=meta["content"],
                    score=final_score,
                    metadata=meta["metadata"]
                ))

                # 更新访问统计
                meta["access_count"] += 1
                meta["last_accessed"] = datetime.utcnow().isoformat()
                await self.metadata.set(f"memory:{meta['id']}", json.dumps(meta))

        # 3. 按分数排序并返回 top_k
        memories.sort(key=lambda m: m.score, reverse=True)
        return memories[:top_k]

    async def cleanup_forgotten_memories(self):
        """清理已遗忘的记忆（定时任务）"""
        all_memory_keys = await self.metadata.keys("memory:*")

        forgotten_count = 0
        for key in all_memory_keys:
            memory_data = await self.metadata.get(key)
            meta = json.loads(memory_data)

            decay_score = self.decay_manager.calculate_decay_score(
                created_at=datetime.fromisoformat(meta["created_at"]),
                importance=meta["importance"],
                access_count=meta["access_count"],
                last_accessed=datetime.fromisoformat(meta["last_accessed"]) if meta["last_accessed"] else None
            )

            if self.decay_manager.should_forget(decay_score):
                await self.metadata.delete(key)
                forgotten_count += 1

        logger.info(f"Cleaned up {forgotten_count} forgotten memories")
        return forgotten_count
```

**定时清理任务**:

```python
# algo/agent-engine/app/tasks/memory_cleanup.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=3, minute=0)  # 每天凌晨 3 点
async def cleanup_forgotten_memories():
    """清理遗忘的记忆"""
    vector_memory = get_vector_memory()  # 依赖注入
    count = await vector_memory.cleanup_forgotten_memories()
    logger.info(f"Memory cleanup completed: {count} memories removed")
```

**验收标准**:

- [ ] 记忆分数随时间递减
- [ ] 重访记忆会增强记忆强度
- [ ] 低分记忆自动清理
- [ ] 重要记忆保留更久
- [ ] 单元测试覆盖衰减算法
- [ ] 性能测试: 1000 记忆召回 < 100ms

---

### Sprint 2: 语音能力提升 (Week 2)

#### 🎯 Sprint 目标

- 集成 Silero VAD 深度学习模型
- 实现流式 VAD 检测
- 提供 VAD 置信度评分

#### 📋 任务清单

##### 4. Silero VAD 深度学习语音检测

**负责人**: AI Team
**预估工时**: 3-5 天
**优先级**: P0

**详细说明**:

- 当前使用基础 VAD（能量检测），准确率约 85%
- voicehelper 使用 Silero VAD 深度学习模型，准确率 > 95%

**实现要点**:

```python
# algo/voice-engine/app/core/vad_engine.py

import torch
import torchaudio
from typing import List, Tuple

class SileroVADEngine:
    """Silero VAD 语音活动检测引擎

    模型: https://github.com/snakers4/silero-vad
    准确率: > 95%
    延迟: < 50ms (CPU)
    """

    def __init__(self, model_path: str = "models/silero_vad.jit", threshold: float = 0.5):
        # 加载模型
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        self.model.eval()

        # 提取工具函数
        (self.get_speech_timestamps,
         self.save_audio,
         self.read_audio,
         self.VADIterator,
         self.collect_chunks) = self.utils

        self.threshold = threshold
        self.sample_rate = 16000

    def detect_speech(self, audio: np.ndarray) -> List[dict]:
        """检测语音段落

        Args:
            audio: 音频数据 (numpy array, 16kHz)

        Returns:
            语音段列表: [
                {'start': 0.5, 'end': 2.3, 'confidence': 0.95},
                ...
            ]
        """
        # 转换为 PyTorch Tensor
        if isinstance(audio, np.ndarray):
            audio_tensor = torch.from_numpy(audio).float()
        else:
            audio_tensor = audio

        # 检测语音时间戳
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=250,  # 最小语音段 250ms
            min_silence_duration_ms=100,  # 最小静音段 100ms
            window_size_samples=512,      # 窗口大小 32ms
            speech_pad_ms=30              # 语音边缘填充 30ms
        )

        # 格式化输出
        segments = []
        for ts in speech_timestamps:
            segments.append({
                'start': ts['start'] / self.sample_rate,
                'end': ts['end'] / self.sample_rate,
                'confidence': self._calculate_confidence(audio_tensor[ts['start']:ts['end']])
            })

        return segments

    def _calculate_confidence(self, audio_chunk: torch.Tensor) -> float:
        """计算语音置信度"""
        with torch.no_grad():
            # 模型输出：语音概率
            speech_prob = self.model(audio_chunk, self.sample_rate).item()
        return speech_prob

    def detect_stream(self, audio_chunk: np.ndarray, context: dict = None) -> Tuple[bool, float, dict]:
        """流式检测（适用于 WebSocket）

        Args:
            audio_chunk: 音频块 (512 samples = 32ms @ 16kHz)
            context: 上下文状态（VAD 需要保持状态）

        Returns:
            (is_speech, confidence, new_context)
        """
        if context is None:
            # 初始化流式检测器
            vad_iterator = self.VADIterator(self.model, threshold=self.threshold)
            context = {'vad_iterator': vad_iterator}

        vad_iterator = context['vad_iterator']

        # 检测当前音频块
        audio_tensor = torch.from_numpy(audio_chunk).float()
        speech_dict = vad_iterator(audio_tensor, return_seconds=False)

        # 解析结果
        if speech_dict:
            is_speech = True
            confidence = self._calculate_confidence(audio_tensor)
        else:
            is_speech = False
            confidence = 0.0

        return is_speech, confidence, context

# FastAPI 路由

from fastapi import UploadFile, File
from pydantic import BaseModel

class VADRequest(BaseModel):
    audio_url: str
    threshold: float = 0.5

class VADSegment(BaseModel):
    start: float
    end: float
    confidence: float

class VADResponse(BaseModel):
    segments: List[VADSegment]
    total_speech_duration: float
    speech_ratio: float

@router.post("/vad/detect", response_model=VADResponse)
async def detect_vad(request: VADRequest):
    """批量 VAD 检测"""
    # 下载音频
    audio = await download_audio(request.audio_url)

    # VAD 检测
    vad_engine = get_vad_engine()
    segments = vad_engine.detect_speech(audio)

    # 统计
    total_duration = len(audio) / vad_engine.sample_rate
    speech_duration = sum(s['end'] - s['start'] for s in segments)
    speech_ratio = speech_duration / total_duration

    return VADResponse(
        segments=[VADSegment(**s) for s in segments],
        total_speech_duration=speech_duration,
        speech_ratio=speech_ratio
    )

@router.websocket("/vad/stream")
async def stream_vad(websocket: WebSocket):
    """流式 VAD (WebSocket)"""
    await websocket.accept()

    vad_engine = get_vad_engine()
    context = None

    try:
        while True:
            # 接收音频块 (512 samples = 32ms)
            audio_chunk = await websocket.receive_bytes()
            audio_array = np.frombuffer(audio_chunk, dtype=np.float32)

            # 流式检测
            is_speech, confidence, context = vad_engine.detect_stream(audio_array, context)

            # 发送结果
            await websocket.send_json({
                "is_speech": is_speech,
                "confidence": float(confidence),
                "timestamp": time.time()
            })

    except WebSocketDisconnect:
        logger.info("VAD WebSocket disconnected")
```

**模型部署**:

```dockerfile
# algo/voice-engine/Dockerfile

FROM python:3.11-slim

# 安装 PyTorch (CPU)
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 下载 Silero VAD 模型
RUN python -c "import torch; torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')"

# ... 其他依赖 ...
```

**性能优化**:

```python
# 批量推理优化
class BatchedVADEngine(SileroVADEngine):
    """批量 VAD 推理（提升吞吐）"""

    def detect_batch(self, audio_list: List[np.ndarray]) -> List[List[dict]]:
        """批量检测"""
        # 填充到相同长度
        max_len = max(len(audio) for audio in audio_list)
        padded_audios = [
            np.pad(audio, (0, max_len - len(audio)), 'constant')
            for audio in audio_list
        ]

        # 批量推理
        audio_tensor = torch.from_numpy(np.stack(padded_audios)).float()

        with torch.no_grad():
            # 并行检测
            results = []
            for audio in audio_tensor:
                segments = self.detect_speech(audio.numpy())
                results.append(segments)

        return results
```

**验收标准**:

- [ ] Silero VAD 模型正确加载
- [ ] 批量检测准确率 > 95%
- [ ] 流式检测延迟 < 50ms (P95)
- [ ] WebSocket 接口稳定运行
- [ ] 置信度评分合理
- [ ] 模型文件大小 < 50MB
- [ ] 内存占用 < 200MB

---

##### 5. 智谱 AI GLM-4 系列模型支持

**负责人**: AI Team
**预估工时**: 2-3 天
**优先级**: P1

[... 详细实现方案 ...]

---

##### 6. 文档版本管理 (MVP)

**负责人**: Backend Team
**预估工时**: 5-7 天
**优先级**: P1

[... 详细实现方案 ...]

---

##### 7. 病毒扫描 (ClamAV)

**负责人**: Backend Team
**预估工时**: 3-5 天
**优先级**: P1

[... 详细实现方案 ...]

---

## 📦 v2.2.0 功能扩展 (Week 4-7)

[... 详细实现方案 ...]

---

## 📦 v2.3.0 优化提升 (Week 8-10)

[... 详细实现方案 ...]

---

## 📊 进度跟踪

| Week | Sprint         | 计划任务            | 状态      | 完成度 |
| ---- | -------------- | ------------------- | --------- | ------ |
| 1    | 系统可靠性     | Redis 任务持久化    | 📋 待开始 | 0%     |
|      |                | 分布式限流器        | 📋 待开始 | 0%     |
|      |                | 记忆时间衰减        | 📋 待开始 | 0%     |
| 2    | 语音能力提升   | Silero VAD          | 📋 待开始 | 0%     |
|      |                | 流式 VAD            | 📋 待开始 | 0%     |
| 3    | 模型与文档增强 | GLM-4 支持          | 📋 待开始 | 0%     |
|      |                | 文档版本管理        | 📋 待开始 | 0%     |
|      |                | 病毒扫描            | 📋 待开始 | 0%     |
| 4-5  | 移动端推送     | FCM/APNs            | 📋 待开始 | 0%     |
| 6-7  | 情感识别       | 声学特征 + 情感分类 | 📋 待开始 | 0%     |
| 8-9  | 开发工具       | CLI 工具 + 部署脚本 | 📋 待开始 | 0%     |
| 10   | 性能优化       | 批量优化 + 格式转换 | 📋 待开始 | 0%     |

---

## 🎯 KPI 与验收

### 技术指标

| 指标               | 基线 (v2.0.0) | 目标 (v2.3.0) | 提升 | 当前 |
| ------------------ | ------------- | ------------- | ---- | ---- |
| VAD 准确率         | ~85%          | > 95%         | +10% | -    |
| 任务持久化         | ❌ 内存       | ✅ Redis      | -    | -    |
| 分布式限流         | ❌ 本地       | ✅ 全局       | -    | -    |
| 模型支持数         | 5 厂商        | 6 厂商        | +1   | -    |
| 文档安全扫描       | ❌            | ✅ ClamAV     | -    | -    |
| 部署时间           | ~30min        | < 5min        | -83% | -    |
| 记忆召回准确率     | ~70%          | > 85%         | +15% | -    |
| 情感识别准确率     | N/A           | > 80%         | -    | -    |
| Push 通知到达率    | N/A           | > 95%         | -    | -    |
| 文档版本管理采用率 | N/A           | > 50%         | -    | -    |

---

## 🚨 风险管理

### 技术风险

| 风险项              | 等级 | 影响                 | 缓解措施                | 责任人  |
| ------------------- | ---- | -------------------- | ----------------------- | ------- |
| Silero VAD 模型体积 | 高   | 镜像体积增加 ~40MB   | 独立模型服务 / 按需加载 | AI Team |
| 情感识别实时性      | 高   | 推理延迟可能 > 200ms | 轻量级模型 / GPU 加速   | AI Team |
| Push 通知合规性     | 中   | 不同地区政策差异     | 区域配置 / 合规审计     | Backend |
| 文档版本存储成本    | 中   | 多版本存储成本上升   | 压缩算法 / 版本数量限制 | Backend |
| Redis 单点故障      | 中   | 任务/限流不可用      | Redis Sentinel 高可用   | SRE     |
| CLI 工具兼容性      | 低   | 不同 OS 脚本差异     | Go 编写跨平台 CLI       | Backend |

---

## 📚 参考资料

### 技术文档

- [Silero VAD GitHub](https://github.com/snakers4/silero-vad)
- [智谱 AI GLM-4 API](https://open.bigmodel.cn/dev/api)
- [ClamAV 官方文档](https://docs.clamav.net/)
- [FCM Documentation](https://firebase.google.com/docs/cloud-messaging)
- [APNs Documentation](https://developer.apple.com/documentation/usernotifications)
- [Redis 分布式限流](https://redis.io/docs/manual/patterns/distributed-locks/)

### voicehelper 参考

- **GitHub**: https://github.com/haoyunlt/voicehelper
- **版本**: v0.9.2
- **对比报告**: `docs/reports/voicehelper-feature-comparison.md`

---

## 📝 变更日志

| 日期       | 版本   | 变更内容 | 作者         |
| ---------- | ------ | -------- | ------------ |
| 2025-10-27 | v1.0.0 | 初始版本 | AI Assistant |

---

**文档所有者**: AI 架构团队
**下次审核**: Sprint 1 结束后
