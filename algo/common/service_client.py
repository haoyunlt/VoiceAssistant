"""
统一服务客户端 - 为 Python 服务间调用提供重试、熔断、超时机制

所有 Python 算法服务间的 HTTP 调用应使用此客户端，确保弹性和一致性。

示例:
    retrieval_client = BaseServiceClient("http://retrieval-service:8012", "retrieval-service")
    result = await retrieval_client.post("/api/v1/retrieval/hybrid", {...})
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from resilience import CircuitBreaker, with_retry

logger = logging.getLogger(__name__)


class BaseServiceClient:
    """
    基础服务客户端

    提供统一的重试、熔断、超时机制
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ):
        """
        初始化服务客户端

        Args:
            base_url: 服务基础 URL (如 http://retrieval-service:8012)
            service_name: 服务名称 (用于日志和监控)
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            circuit_breaker_threshold: 熔断器失败阈值
            circuit_breaker_timeout: 熔断器恢复时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.timeout = timeout
        self.max_retries = max_retries

        # 初始化熔断器
        self.circuit_breaker = CircuitBreaker(
            name=service_name,
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
            expected_exception=(httpx.HTTPError, httpx.TimeoutException),
        )

        # 统计信息
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retries": 0,
        }

        logger.info(
            f"BaseServiceClient initialized: {service_name} at {base_url}, "
            f"timeout={timeout}s, max_retries={max_retries}"
        )

    async def get(
        self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        发送 GET 请求

        Args:
            path: 请求路径 (如 /api/v1/health)
            params: 查询参数
            headers: 额外的请求头

        Returns:
            响应 JSON 数据

        Raises:
            httpx.HTTPError: HTTP 错误
            Exception: 熔断器打开或其他错误
        """
        return await self._request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        发送 POST 请求

        Args:
            path: 请求路径
            json: 请求 JSON 数据
            params: 查询参数
            headers: 额外的请求头

        Returns:
            响应 JSON 数据
        """
        return await self._request("POST", path, json=json, params=params, headers=headers)

    async def put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """发送 PUT 请求"""
        return await self._request("PUT", path, json=json, params=params, headers=headers)

    async def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """发送 DELETE 请求"""
        return await self._request("DELETE", path, params=params, headers=headers)

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        发送 HTTP 请求（带重试和熔断）

        Args:
            method: HTTP 方法
            path: 请求路径
            json: JSON 数据
            params: 查询参数
            headers: 请求头

        Returns:
            响应 JSON 数据
        """
        url = f"{self.base_url}{path}"
        self.stats["total_requests"] += 1

        # 准备请求头
        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Service-Name": self.service_name,
        }
        if headers:
            req_headers.update(headers)

        # 注入 trace context
        try:
            from trace_propagation import inject_trace_headers
            req_headers = inject_trace_headers(req_headers)
        except Exception:
            # 如果 OpenTelemetry 未配置，忽略错误
            pass

        # 定义请求函数（用于重试和熔断）
        @with_retry(
            max_attempts=self.max_retries,
            exceptions=(httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError),
            on_retry=self._on_retry,
        )
        async def _do_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method, url=url, json=json, params=params, headers=req_headers
                )
                response.raise_for_status()
                return response.json()

        # 通过熔断器执行
        try:
            start_time = time.time()
            result = await self.circuit_breaker.call_async(_do_request)
            elapsed = time.time() - start_time

            self.stats["successful_requests"] += 1
            logger.debug(
                f"{self.service_name} {method} {path} succeeded in {elapsed:.2f}s"
            )

            return result

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(
                f"{self.service_name} {method} {path} failed: {e}",
                extra={
                    "service": self.service_name,
                    "method": method,
                    "path": path,
                    "error": str(e),
                },
            )
            raise

    def _on_retry(self, attempt: int, exception: Exception):
        """重试回调"""
        self.stats["retries"] += 1
        logger.warning(
            f"{self.service_name} retry {attempt}/{self.max_retries}: {exception}"
        )

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            是否健康
        """
        try:
            response = await self.get("/health")
            return response.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"{self.service_name} health check failed: {e}")
            return False

    async def readiness_check(self) -> tuple[bool, dict[str, Any]]:
        """
        就绪检查

        Returns:
            (是否就绪, 详细检查结果)
        """
        try:
            response = await self.get("/ready")
            ready = response.get("ready", False)
            checks = response.get("checks", {})
            return ready, checks
        except Exception as e:
            logger.warning(f"{self.service_name} readiness check failed: {e}")
            return False, {"error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        success_rate = (
            self.stats["successful_requests"] / self.stats["total_requests"]
            if self.stats["total_requests"] > 0
            else 0
        )

        return {
            "service_name": self.service_name,
            "base_url": self.base_url,
            "total_requests": self.stats["total_requests"],
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "retries": self.stats["retries"],
            "success_rate": success_rate,
            "circuit_breaker": self.circuit_breaker.get_stats(),
        }

    def get_circuit_breaker_state(self) -> str:
        """获取熔断器状态"""
        return self.circuit_breaker.state.value


# 全局客户端管理器
_clients: dict[str, BaseServiceClient] = {}


def get_client(service_name: str, base_url: str, **kwargs) -> BaseServiceClient:
    """
    获取或创建服务客户端（单例）

    Args:
        service_name: 服务名称
        base_url: 服务 URL
        **kwargs: 额外参数传递给 BaseServiceClient

    Returns:
        服务客户端实例
    """
    key = f"{service_name}:{base_url}"
    if key not in _clients:
        _clients[key] = BaseServiceClient(base_url, service_name, **kwargs)
    return _clients[key]


def get_all_clients() -> dict[str, BaseServiceClient]:
    """获取所有已创建的客户端"""
    return _clients.copy()


def get_all_stats() -> dict[str, dict[str, Any]]:
    """获取所有客户端的统计信息"""
    return {key: client.get_stats() for key, client in _clients.items()}
