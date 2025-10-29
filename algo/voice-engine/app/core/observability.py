"""
Observability - Prometheus 指标和链路追踪
"""

import logging
import time
from collections.abc import Callable
from functools import wraps

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ===== Prometheus 指标 =====

# ASR 指标
asr_requests_total = Counter(
    "asr_requests_total",
    "Total number of ASR requests",
    ["model", "language", "status"],
)

asr_duration_seconds = Histogram(
    "asr_duration_seconds",
    "ASR processing duration in seconds",
    ["model", "language"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

asr_audio_duration_seconds = Histogram(
    "asr_audio_duration_seconds",
    "Duration of audio processed by ASR in seconds",
    ["model", "language"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

# TTS 指标
tts_requests_total = Counter(
    "tts_requests_total",
    "Total number of TTS requests",
    ["voice", "provider", "status"],
)

tts_duration_seconds = Histogram(
    "tts_duration_seconds",
    "TTS processing duration in seconds",
    ["voice", "provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

tts_text_length = Histogram(
    "tts_text_length",
    "Length of text for TTS",
    ["voice"],
    buckets=(10, 50, 100, 200, 500, 1000, 2000),
)

tts_cache_hits_total = Counter(
    "tts_cache_hits_total",
    "Total number of TTS cache hits",
    ["voice"],
)

tts_cache_misses_total = Counter(
    "tts_cache_misses_total",
    "Total number of TTS cache misses",
    ["voice"],
)

# VAD 指标
vad_requests_total = Counter(
    "vad_requests_total",
    "Total number of VAD requests",
    ["status"],
)

vad_duration_seconds = Histogram(
    "vad_duration_seconds",
    "VAD processing duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
)

vad_speech_ratio = Histogram(
    "vad_speech_ratio",
    "Ratio of speech in audio",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0),
)

# 系统指标
active_connections = Gauge(
    "active_connections",
    "Number of active WebSocket connections",
)

memory_usage_bytes = Gauge(
    "memory_usage_bytes",
    "Memory usage in bytes",
)

# 错误指标
errors_total = Counter(
    "errors_total",
    "Total number of errors",
    ["service", "error_type"],
)


# ===== 指标装饰器 =====


def track_asr_metrics(model: str = "base", language: str = "zh"):
    """ASR 指标追踪装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                # 记录成功指标
                asr_requests_total.labels(
                    model=model, language=language, status="success"
                ).inc()

                duration = time.time() - start_time
                asr_duration_seconds.labels(model=model, language=language).observe(
                    duration
                )

                # 如果结果包含音频时长
                if isinstance(result, dict) and "duration_seconds" in result:
                    asr_audio_duration_seconds.labels(
                        model=model, language=language
                    ).observe(result["duration_seconds"])

                return result

            except Exception as e:
                # 记录失败指标
                asr_requests_total.labels(
                    model=model, language=language, status="error"
                ).inc()

                errors_total.labels(service="asr", error_type=type(e).__name__).inc()

                raise

        return wrapper

    return decorator


def track_tts_metrics(voice: str = "default", provider: str = "edge"):
    """TTS 指标追踪装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            # 记录文本长度
            if "text" in kwargs:
                text = kwargs["text"]
                tts_text_length.labels(voice=voice).observe(len(text))

            try:
                result = await func(*args, **kwargs)

                # 记录成功指标
                tts_requests_total.labels(
                    voice=voice, provider=provider, status="success"
                ).inc()

                duration = time.time() - start_time
                tts_duration_seconds.labels(voice=voice, provider=provider).observe(
                    duration
                )

                # 记录缓存命中
                if isinstance(result, dict) and result.get("cached"):
                    tts_cache_hits_total.labels(voice=voice).inc()
                else:
                    tts_cache_misses_total.labels(voice=voice).inc()

                return result

            except Exception as e:
                # 记录失败指标
                tts_requests_total.labels(
                    voice=voice, provider=provider, status="error"
                ).inc()

                errors_total.labels(service="tts", error_type=type(e).__name__).inc()

                raise

        return wrapper

    return decorator


def track_vad_metrics():
    """VAD 指标追踪装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                # 记录成功指标
                vad_requests_total.labels(status="success").inc()

                duration = time.time() - start_time
                vad_duration_seconds.observe(duration)

                # 如果结果包含语音比例
                if isinstance(result, dict) and "speech_ratio" in result:
                    vad_speech_ratio.observe(result["speech_ratio"])

                return result

            except Exception as e:
                # 记录失败指标
                vad_requests_total.labels(status="error").inc()

                errors_total.labels(service="vad", error_type=type(e).__name__).inc()

                raise

        return wrapper

    return decorator


# ===== 工具函数 =====


def get_metrics_summary() -> dict:
    """获取指标摘要"""
    from prometheus_client import REGISTRY

    metrics = {}

    for collector in REGISTRY._collector_to_names:
        try:
            for metric in collector.collect():
                metrics[metric.name] = {
                    "type": metric.type,
                    "documentation": metric.documentation,
                }
        except Exception:
            pass

    return metrics
