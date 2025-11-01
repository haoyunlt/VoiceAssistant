"""
监控端点 - 提供熔断器和服务状态查询

在 FastAPI 应用中使用:
    from common.monitoring_endpoints import router as monitoring_router
    app.include_router(monitoring_router)
"""

import logging
from typing import Any

from fastapi import APIRouter

from service_client import get_all_clients, get_all_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/circuit-breakers", summary="获取所有服务的熔断器状态")
async def get_circuit_breakers() -> dict[str, Any]:
    """
    获取所有已注册服务客户端的熔断器状态

    Returns:
        熔断器状态字典
    """
    clients = get_all_clients()
    circuit_breakers = {}

    for key, client in clients.items():
        cb_stats = client.circuit_breaker.get_stats()
        circuit_breakers[key] = {
            "service": client.service_name,
            "state": client.get_circuit_breaker_state(),
            "stats": cb_stats,
        }

    return {
        "total_services": len(circuit_breakers),
        "circuit_breakers": circuit_breakers,
    }


@router.get("/clients/stats", summary="获取所有服务客户端的统计信息")
async def get_clients_stats() -> dict[str, Any]:
    """
    获取所有服务客户端的请求统计

    Returns:
        统计信息字典
    """
    stats = get_all_stats()

    # 计算总体统计
    total_requests = sum(s["total_requests"] for s in stats.values())
    total_successful = sum(s["successful_requests"] for s in stats.values())
    total_failed = sum(s["failed_requests"] for s in stats.values())
    total_retries = sum(s["retries"] for s in stats.values())

    return {
        "total": {
            "requests": total_requests,
            "successful": total_successful,
            "failed": total_failed,
            "retries": total_retries,
            "success_rate": (
                total_successful / total_requests if total_requests > 0 else 0
            ),
        },
        "services": stats,
    }


@router.get("/health/dependencies", summary="检查所有依赖服务的健康状态")
async def check_dependencies_health() -> dict[str, Any]:
    """
    并发检查所有依赖服务的健康状态

    Returns:
        健康状态字典
    """
    import asyncio

    clients = get_all_clients()
    health_checks = {}

    async def check_health(key: str, client: Any) -> tuple[str, bool]:
        try:
            is_healthy = await client.health_check()
            return key, is_healthy
        except Exception as e:
            logger.warning(f"Health check failed for {key}: {e}")
            return key, False

    # 并发执行健康检查
    tasks = [check_health(key, client) for key, client in clients.items()]
    results = await asyncio.gather(*tasks)

    for key, is_healthy in results:
        health_checks[key] = {
            "healthy": is_healthy,
            "service": clients[key].service_name,
        }

    all_healthy = all(status["healthy"] for status in health_checks.values())

    return {
        "all_healthy": all_healthy,
        "total_services": len(health_checks),
        "healthy_count": sum(1 for s in health_checks.values() if s["healthy"]),
        "services": health_checks,
    }
