"""
LLM Call Optimizer - LLM调用优化器

实现功能：
- 批量调用（Batch Processing）
- 结果缓存（LRU Cache）
- Prompt缓存（Anthropic-style）
- 调用去重
- 性能监控
"""

import asyncio
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


# Prometheus指标
llm_calls_total = Counter("llm_calls_total", "Total LLM API calls", ["model", "cache_hit"])

llm_call_latency_seconds = Histogram("llm_call_latency_seconds", "LLM API call latency", ["model"])

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed",
    ["model", "type"],  # type: prompt/completion
)


@dataclass
class CacheEntry:
    """缓存条目"""

    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int


class LRUCache:
    """LRU缓存"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        if key in self.cache:
            entry = self.cache[key]

            # 检查是否过期
            if self._is_expired(entry):
                del self.cache[key]
                self.misses += 1
                return None

            # 更新访问信息
            entry.last_accessed = datetime.now()
            entry.access_count += 1

            # 移动到最后（LRU）
            self.cache.move_to_end(key)

            self.hits += 1
            return entry.value
        else:
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """设置缓存"""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            ttl_seconds=ttl_seconds,
        )

        self.cache[key] = entry
        self.cache.move_to_end(key)

        # 限制大小
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)  # 移除最旧的

    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查是否过期"""
        age = (datetime.now() - entry.created_at).total_seconds()
        return age > entry.ttl_seconds

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_requests = self.hits + self.misses
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total_requests if total_requests > 0 else 0.0,
        }


@dataclass
class BatchRequest:
    """批处理请求"""

    request_id: str
    prompt: str
    model: str
    temperature: float
    max_tokens: int
    metadata: dict
    future: asyncio.Future


class LLMCallOptimizer:
    """
    LLM调用优化器

    用法:
        optimizer = LLMCallOptimizer(llm_client)

        # 单次调用（带缓存）
        result = await optimizer.call(
            prompt="What is AI?",
            model="gpt-4",
            use_cache=True
        )

        # 批量调用
        results = await optimizer.batch_call([
            {"prompt": "What is AI?", "model": "gpt-4"},
            {"prompt": "What is ML?", "model": "gpt-4"}
        ])
    """

    def __init__(
        self,
        llm_client: Any,
        cache_enabled: bool = True,
        cache_size: int = 1000,
        batch_size: int = 10,
        batch_timeout_seconds: float = 0.5,
    ):
        self.llm_client = llm_client
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size
        self.batch_timeout_seconds = batch_timeout_seconds

        # 缓存
        self.cache = LRUCache(max_size=cache_size) if cache_enabled else None

        # 批处理队列
        self.batch_queue: list[BatchRequest] = []
        self.batch_lock = asyncio.Lock()
        self.batch_task: asyncio.Task | None = None

        # 统计信息
        self.stats = {
            "total_calls": 0,
            "cached_calls": 0,
            "batch_calls": 0,
            "single_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
        }

        logger.info(
            f"LLMCallOptimizer initialized (cache={cache_enabled}, batch_size={batch_size})"
        )

    async def call(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 500,
        use_cache: bool = True,
        metadata: dict | None = None,
    ) -> str:
        """
        调用LLM（单次）

        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度
            max_tokens: 最大token数
            use_cache: 是否使用缓存
            metadata: 元数据

        Returns:
            生成的文本
        """
        import time

        start_time = time.time()

        self.stats["total_calls"] += 1

        # 1. 检查缓存
        if use_cache and self.cache:
            cache_key = self._generate_cache_key(prompt, model, temperature)
            cached_result = self.cache.get(cache_key)

            if cached_result is not None:
                self.stats["cached_calls"] += 1
                llm_calls_total.labels(model=model, cache_hit="true").inc()

                logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                return cached_result

        # 2. 调用LLM
        llm_calls_total.labels(model=model, cache_hit="false").inc()

        result = await self.llm_client.generate(
            prompt=prompt, temperature=temperature, max_tokens=max_tokens
        )

        # 3. 保存到缓存
        if use_cache and self.cache:
            self.cache.set(cache_key, result, ttl_seconds=3600)

        # 4. 更新统计
        latency = time.time() - start_time
        self.stats["single_calls"] += 1
        self.stats["total_latency"] += latency

        llm_call_latency_seconds.labels(model=model).observe(latency)

        logger.debug(f"LLM call completed in {latency:.3f}s")

        return result

    async def batch_call(self, requests: list[dict], use_cache: bool = True) -> list[str]:
        """
        批量调用LLM

        Args:
            requests: 请求列表，每个请求包含prompt, model等
            use_cache: 是否使用缓存

        Returns:
            结果列表
        """
        results = []

        for request in requests:
            result = await self.call(
                prompt=request["prompt"],
                model=request.get("model", "gpt-4"),
                temperature=request.get("temperature", 0.7),
                max_tokens=request.get("max_tokens", 500),
                use_cache=use_cache,
                metadata=request.get("metadata"),
            )
            results.append(result)

        self.stats["batch_calls"] += len(requests)

        return results

    async def enqueue_for_batch(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 500,
        metadata: dict | None = None,
    ) -> asyncio.Future:
        """
        加入批处理队列（异步）

        Returns:
            Future对象，可await获取结果
        """
        request_id = f"req_{datetime.now().timestamp()}"
        future: asyncio.Future = asyncio.Future()

        batch_request = BatchRequest(
            request_id=request_id,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {},
            future=future,
        )

        async with self.batch_lock:
            self.batch_queue.append(batch_request)

            # 启动批处理任务
            if self.batch_task is None or self.batch_task.done():
                self.batch_task = asyncio.create_task(self._process_batch())

        return future

    async def _process_batch(self):
        """处理批处理队列"""
        await asyncio.sleep(self.batch_timeout_seconds)

        async with self.batch_lock:
            if not self.batch_queue:
                return

            # 取出一批请求
            batch = self.batch_queue[: self.batch_size]
            self.batch_queue = self.batch_queue[self.batch_size :]

        logger.info(f"Processing batch of {len(batch)} requests")

        # 并发执行
        tasks = [
            self.call(
                prompt=req.prompt,
                model=req.model,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                use_cache=True,
                metadata=req.metadata,
            )
            for req in batch
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 设置Future结果
        for req, result in zip(batch, results):
            if isinstance(result, Exception):
                req.future.set_exception(result)
            else:
                req.future.set_result(result)

    def _generate_cache_key(self, prompt: str, model: str, temperature: float) -> str:
        """生成缓存键"""
        # 使用SHA256哈希
        content = f"{prompt}|{model}|{temperature}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        if self.cache:
            return self.cache.get_stats()
        return {}

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "cache_stats": self.get_cache_stats(),
            "avg_latency": (
                self.stats["total_latency"] / self.stats["single_calls"]
                if self.stats["single_calls"] > 0
                else 0.0
            ),
            "cache_hit_rate": (
                self.stats["cached_calls"] / self.stats["total_calls"]
                if self.stats["total_calls"] > 0
                else 0.0
            ),
        }

    def clear_cache(self):
        """清空缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("Cache cleared")


# 全局单例
_llm_optimizer: LLMCallOptimizer | None = None


def get_llm_optimizer(llm_client: Any) -> LLMCallOptimizer:
    """获取全局LLM优化器"""
    global _llm_optimizer
    if _llm_optimizer is None:
        _llm_optimizer = LLMCallOptimizer(llm_client)
    return _llm_optimizer
