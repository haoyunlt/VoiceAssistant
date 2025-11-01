"""
RAG Engine - 检索增强生成引擎

核心功能：
- 查询改写（Query Rewriting）
- 检索调用（Retrieval Integration）
- 上下文构建（Context Building）
- Prompt 生成（Prompt Generation）
- 答案生成（Answer Generation with LLM）
- 引用来源（Citation & Source Tracking）

集成：
- 统一配置管理（Nacos/本地/环境变量）
- 统一错误码规范（全局错误码体系）
- 错误监控和指标收集（Prometheus）
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

# 添加common目录到Python路径
_common_path = Path(__file__).parent.parent / "common"
if str(_common_path) not in sys.path:
    sys.path.insert(0, str(_common_path))

# 导入统一基础设施模块
from config_audit import ConfigAuditLogger  # noqa: E402
from cors_config import get_cors_config  # noqa: E402
from cost_tracking import cost_tracking_middleware  # noqa: E402
from error_monitoring import get_error_monitor  # noqa: E402
from exception_handlers import register_exception_handlers  # noqa: E402
from structured_logging import logging_middleware, setup_logging  # noqa: E402
from telemetry import TracingConfig, init_tracing  # noqa: E402

# 导入统一配置管理和错误监控
from unified_config import create_config  # noqa: E402

# 配置统一日志
setup_logging(service_name="rag-engine")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理（集成统一配置和错误监控）"""
    logger.info("Starting RAG Engine...")

    try:
        # 1. 加载统一配置
        config = create_config(
            service_name="rag-engine",
            config_path="./configs/rag-engine.yaml",
            required_keys=["server.host", "server.port"]
        )
        _app.state.config = config
        logger.info("Unified config loaded")

        # 2. 启动配置审计日志
        audit_logger = ConfigAuditLogger("rag-engine", enable_audit=True)
        _app.state.audit_logger = audit_logger
        audit_logger.log_config_load(
            source="unified",
            success=True,
            config_keys=list(config._config_data.keys())
        )

        # 3. 启动错误监控
        error_monitor = get_error_monitor("rag-engine")
        _app.state.error_monitor = error_monitor
        logger.info("Error monitoring initialized")

        # 4. 初始化 OpenTelemetry 追踪
        tracing_config = TracingConfig(
            service_name="rag-engine",
            service_version=config.get_string("service.version", "1.0.0"),
            environment=config.get_string("service.environment", "development"),
        )
        tracer = init_tracing(tracing_config)
        if tracer:
            logger.info("OpenTelemetry tracing initialized")

        # 5. 初始化 RAG 服务
        from app.routers.rag import init_rag_service
        from app.routers.ultimate_rag import init_ultimate_rag_service

        init_rag_service()

        # 初始化 Ultimate RAG 服务 (v2.0)
        try:
            init_ultimate_rag_service()
            logger.info("Ultimate RAG v2.0 initialized")
        except Exception as e:
            logger.warning(f"Ultimate RAG v2.0 initialization failed: {e}")
            logger.info("Falling back to RAG v1.0")

        logger.info("RAG Engine started successfully with unified config and error monitoring")

        yield

    finally:
        logger.info("Shutting down RAG Engine...")

        # 清理资源
        from app.routers.rag import rag_service

        if rag_service:
            await rag_service.close()

        logger.info("RAG Engine shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Engine",
    description="检索增强生成引擎 - 查询改写、上下文构建、答案生成、引用来源",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（使用统一配置）
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# 日志中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# 成本追踪中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
from app.routers import rag as rag_router  # noqa: E402
from app.routers import ultimate_rag  # noqa: E402

app.include_router(rag_router.router, prefix="/api/v1")
app.include_router(ultimate_rag.router, prefix="/api")

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "rag-engine"}


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8006"))  # 统一使用8006端口
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port} with {workers} workers")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )
