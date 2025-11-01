"""
Statistics tracking utilities
"""

import time
from collections import deque
from typing import Any


class StatsTracker:
    """Thread-safe statistics tracker with bounded memory"""

    def __init__(self, max_latency_samples: int = 1000):
        """
        Initialize stats tracker

        Args:
            max_latency_samples: Maximum number of latency samples to keep
        """
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Use deque with maxlen to prevent unbounded growth
        self._latencies = deque(maxlen=max_latency_samples)
        self._start_time = time.time()

    def record_success(self, latency_ms: float):
        """Record a successful request"""
        self.total_requests += 1
        self.successful_requests += 1
        self._latencies.append(latency_ms)

    def record_failure(self):
        """Record a failed request"""
        self.total_requests += 1
        self.failed_requests += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics"""
        latencies = list(self._latencies)

        stats = {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
            ),
            "uptime_seconds": time.time() - self._start_time,
        }

        if latencies:
            stats.update(
                {
                    "avg_latency_ms": sum(latencies) / len(latencies),
                    "min_latency_ms": min(latencies),
                    "max_latency_ms": max(latencies),
                    "p50_latency_ms": self._percentile(latencies, 0.5),
                    "p95_latency_ms": self._percentile(latencies, 0.95),
                    "p99_latency_ms": self._percentile(latencies, 0.99),
                }
            )
        else:
            stats.update(
                {
                    "avg_latency_ms": 0.0,
                    "min_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "p50_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                }
            )

        return stats

    @staticmethod
    def _percentile(data: list, percentile: float) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def reset(self):
        """Reset all statistics"""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self._latencies.clear()
        self._start_time = time.time()
