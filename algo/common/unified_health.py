"""
统一健康检查格式 - Python版本

与Go服务保持一致的健康检查格式
"""

import asyncio
import platform
import sys
import time
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional

import psutil
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """健康状态枚举"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """依赖服务健康状态"""

    status: HealthStatus = Field(..., description="健康状态")
    latency: Optional[int] = Field(None, description="响应延迟（毫秒）")
    message: Optional[str] = Field(None, description="状态消息")
    last_check: Optional[str] = Field(None, description="最后检查时间")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "latency": 15,
                "message": "OK",
                "last_check": "2025-11-01T10:30:00Z",
            }
        }


class SystemInfo(BaseModel):
    """系统信息"""

    python_version: Optional[str] = Field(None, description="Python版本")
    os: Optional[str] = Field(None, description="操作系统")
    arch: Optional[str] = Field(None, description="架构")
    cpu_usage: Optional[float] = Field(None, description="CPU使用率（%）")
    memory_usage: Optional[float] = Field(None, description="内存使用率（%）")
    process_memory: Optional[float] = Field(None, description="进程内存（MB）")

    class Config:
        json_schema_extra = {
            "example": {
                "python_version": "3.11.5",
                "os": "Linux",
                "arch": "x86_64",
                "cpu_usage": 45.2,
                "memory_usage": 62.8,
                "process_memory": 512.5,
            }
        }


class UnifiedHealthResponse(BaseModel):
    """统一健康检查响应"""

    status: HealthStatus = Field(..., description="健康状态")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="服务版本")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z", description="时间戳"
    )
    uptime: int = Field(..., description="运行时间（秒）")

    # 可选字段
    dependencies: Optional[Dict[str, DependencyHealth]] = Field(None, description="依赖服务健康状态")
    system: Optional[SystemInfo] = Field(None, description="系统信息")
    message: Optional[str] = Field(None, description="附加消息")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "agent-engine",
                "version": "1.0.0",
                "timestamp": "2025-11-01T10:30:00Z",
                "uptime": 3600,
                "dependencies": {
                    "redis": {
                        "status": "healthy",
                        "latency": 2,
                        "message": "OK",
                    }
                },
            }
        }


class ReadinessResponse(BaseModel):
    """就绪检查响应"""

    ready: bool = Field(..., description="是否就绪")
    service: str = Field(..., description="服务名称")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z", description="时间戳"
    )
    checks: Dict[str, bool] = Field(default_factory=dict, description="各项检查结果")
    dependencies: Optional[Dict[str, DependencyHealth]] = Field(None, description="依赖状态")
    message: Optional[str] = Field(None, description="附加消息")

    class Config:
        json_schema_extra = {
            "example": {
                "ready": True,
                "service": "agent-engine",
                "timestamp": "2025-11-01T10:30:00Z",
                "checks": {
                    "database": True,
                    "redis": True,
                    "llm": True,
                },
            }
        }


class HealthChecker:
    """健康检查器"""

    def __init__(self, service_name: str, version: str, start_time: float | None = None):
        """
        初始化健康检查器

        Args:
            service_name: 服务名称
            version: 服务版本
            start_time: 启动时间（时间戳）
        """
        self.service_name = service_name
        self.version = version
        self.start_time = start_time or time.time()

    def get_uptime(self) -> int:
        """获取运行时间（秒）"""
        return int(time.time() - self.start_time)

    def get_system_info(self) -> SystemInfo:
        """获取系统信息"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / 1024 / 1024

            return SystemInfo(
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                os=platform.system(),
                arch=platform.machine(),
                cpu_usage=round(cpu_percent, 2),
                memory_usage=round(memory.percent, 2),
                process_memory=round(process_memory_mb, 2),
            )
        except Exception:
            return SystemInfo(
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                os=platform.system(),
                arch=platform.machine(),
            )

    async def check_dependency(
        self,
        name: str,
        check_fn: Callable[[], bool] | Callable[[], asyncio.Future],
        timeout: float = 5.0,
    ) -> DependencyHealth:
        """
        检查依赖服务

        Args:
            name: 依赖服务名称
            check_fn: 检查函数
            timeout: 超时时间（秒）

        Returns:
            依赖健康状态
        """
        start_time = time.time()

        try:
            # 检查函数是否是协程
            import inspect

            if inspect.iscoroutinefunction(check_fn):
                result = await asyncio.wait_for(check_fn(), timeout=timeout)
            else:
                result = check_fn()

            latency = int((time.time() - start_time) * 1000)

            return DependencyHealth(
                status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                latency=latency,
                message="OK" if result else "Check failed",
                last_check=datetime.utcnow().isoformat() + "Z",
            )

        except asyncio.TimeoutError:
            latency = int(timeout * 1000)
            return DependencyHealth(
                status=HealthStatus.UNHEALTHY,
                latency=latency,
                message="Timeout",
                last_check=datetime.utcnow().isoformat() + "Z",
            )

        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            return DependencyHealth(
                status=HealthStatus.UNHEALTHY,
                latency=latency,
                message=str(e),
                last_check=datetime.utcnow().isoformat() + "Z",
            )

    async def check(
        self,
        dependencies: Dict[str, Callable] | None = None,
        include_system: bool = True,
    ) -> UnifiedHealthResponse:
        """
        执行健康检查

        Args:
            dependencies: 依赖检查函数字典
            include_system: 是否包含系统信息

        Returns:
            健康检查响应
        """
        # 检查依赖
        dep_health = {}
        if dependencies:
            for name, check_fn in dependencies.items():
                dep_health[name] = await self.check_dependency(name, check_fn)

        # 确定整体状态
        status = HealthStatus.HEALTHY
        if dep_health:
            has_unhealthy = any(d.status == HealthStatus.UNHEALTHY for d in dep_health.values())
            has_degraded = any(d.status == HealthStatus.DEGRADED for d in dep_health.values())

            if has_unhealthy:
                status = HealthStatus.UNHEALTHY
            elif has_degraded:
                status = HealthStatus.DEGRADED

        # 构建响应
        response = UnifiedHealthResponse(
            status=status,
            service=self.service_name,
            version=self.version,
            uptime=self.get_uptime(),
            dependencies=dep_health if dep_health else None,
            system=self.get_system_info() if include_system else None,
        )

        return response

    async def is_ready(
        self,
        checks: Dict[str, Callable] | None = None,
        dependencies: Dict[str, Callable] | None = None,
    ) -> ReadinessResponse:
        """
        检查是否就绪

        Args:
            checks: 检查项函数字典
            dependencies: 依赖检查函数字典

        Returns:
            就绪检查响应
        """
        # 执行各项检查
        check_results = {}
        if checks:
            for name, check_fn in checks.items():
                try:
                    import inspect

                    if inspect.iscoroutinefunction(check_fn):
                        result = await check_fn()
                    else:
                        result = check_fn()
                    check_results[name] = bool(result)
                except Exception:
                    check_results[name] = False

        # 检查依赖
        dep_health = {}
        if dependencies:
            for name, check_fn in dependencies.items():
                dep_health[name] = await self.check_dependency(name, check_fn)

        # 确定是否就绪
        ready = all(check_results.values()) if check_results else True

        # 如果有不健康的依赖，也标记为不就绪
        if dep_health and any(d.status == HealthStatus.UNHEALTHY for d in dep_health.values()):
            ready = False

        return ReadinessResponse(
            ready=ready,
            service=self.service_name,
            checks=check_results,
            dependencies=dep_health if dep_health else None,
        )


# 标准健康检查项名称
class StandardHealthChecks:
    """标准健康检查项"""

    DATABASE = "database"
    REDIS = "redis"
    MESSAGE_QUEUE = "message_queue"
    EXTERNAL_API = "external_api"
    FILE_STORAGE = "file_storage"
    VECTOR_DB = "vector_db"
    GRAPH_DB = "graph_db"
    SEARCH_ENGINE = "search_engine"
    LLM = "llm"
    EMBEDDING = "embedding"


# FastAPI集成示例
"""
from fastapi import FastAPI
from unified_health import HealthChecker, StandardHealthChecks

app = FastAPI()
health_checker = HealthChecker("my-service", "1.0.0")

@app.get("/health")
async def health():
    '''健康检查'''
    return await health_checker.check(
        dependencies={
            StandardHealthChecks.REDIS: lambda: redis_client.ping(),
            StandardHealthChecks.DATABASE: lambda: db.is_connected(),
        }
    )

@app.get("/ready")
async def readiness():
    '''就绪检查'''
    return await health_checker.is_ready(
        checks={
            "llm": lambda: llm_client is not None,
            "tools": lambda: tool_registry is not None,
        },
        dependencies={
            StandardHealthChecks.REDIS: lambda: redis_client.ping(),
        }
    )
"""

