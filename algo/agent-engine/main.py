"""
Agent Engine - 智能代理引擎（重构版）

核心功能：
- LangGraph 工作流引擎
- ReAct 模式（Reasoning + Acting）
- Plan-Execute 模式
- 工具注册表与调用
- 记忆管理（短期 + 长期）
- 多步骤任务编排
- 支持本地配置和 Nacos 配置中心两种模式
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

# 添加 common 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

# 导入统一基础设施模块
# 导入应用模块
from app.api.dependencies import (
    check_permissions,
    get_agent_engine,
    get_config_manager,
    get_request_id,
    get_tenant_id,
    get_tool_registry,
    optional_verify_token,
    verify_token,
)
from app.api.exception_handlers import register_exception_handlers
from app.core.exceptions import (
    ToolNotFoundError,
    ToolRegistrationError,
)
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware
from app.models.requests import (
    ExecuteTaskRequest,
    ExecuteTaskStreamRequest,
    RegisterToolRequest,
)
from app.models.responses import (
    ConfigInfoResponse,
    ExecuteTaskResponse,
    HealthResponse,
    ListToolsResponse,
    ReadinessCheck,
    ReadinessResponse,
    RegisterToolResponse,
    StatsResponse,
    UnregisterToolResponse,
)
from app.routers import executor as executor_router
from app.routers import llm as llm_router
from app.routers import memory as memory_router
from app.routers import multi_agent as multi_agent_router
from app.routers import permissions as permissions_router
from app.routers import self_rag as self_rag_router
from app.routers import smart_memory as smart_memory_router
from app.routers import tools as tools_router
from app.routers import websocket as websocket_router
from cors_config import get_cors_config
from cost_tracking import cost_tracking_middleware
from structured_logging import logging_middleware, setup_logging
from telemetry import TracingConfig, init_tracing

# 配置统一日志
setup_logging(service_name="agent-engine")
logger = logging.getLogger(__name__)

# 尝试导入 Nacos 配置（可选）
try:
    from nacos_config import get_config_manager as get_nacos_manager
    from nacos_config import init_config

    NACOS_AVAILABLE = True
except ImportError:
    NACOS_AVAILABLE = False
    logger.warning("Nacos support not available, using environment variables only")

# Prometheus 指标
task_counter = Counter(
    "agent_tasks_total", "Total number of agent tasks", ["mode", "status", "tenant_id"]
)
task_duration = Histogram(
    "agent_task_duration_seconds", "Task execution duration", ["mode", "tenant_id"]
)
tool_calls_counter = Counter("agent_tool_calls_total", "Total tool calls", ["tool_name", "status"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Agent Engine...")

    try:
        # 初始化 OpenTelemetry 追踪
        tracing_config = TracingConfig(
            service_name="agent-engine",
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENV", "development"),
        )
        tracer = init_tracing(tracing_config)
        if tracer:
            logger.info("OpenTelemetry tracing initialized")

        # 1. 加载配置（支持 Nacos 或纯环境变量）
        config_data = {}
        use_nacos = os.getenv("USE_NACOS", "false").lower() == "true"

        if use_nacos and NACOS_AVAILABLE:
            config_path = os.getenv("CONFIG_PATH", "./configs/agent-engine.yaml")
            service_name = "agent-engine"

            logger.info(f"Loading config from Nacos: {config_path}")
            config_data = init_config(config_path, service_name)
            app.state.config_manager = get_nacos_manager()

            logger.info(f"Config mode: {app.state.config_manager.get_mode()}")
            logger.info(f"Service name: {config_data.get('service', {}).get('name', service_name)}")
        else:
            logger.info("Using environment variables for configuration")
            app.state.config_manager = None
            config_data = {
                "milvus": {},
                "memory": {},
                "embedding": {},
            }

        # 2. 初始化工具注册表
        from app.tools.dynamic_registry import get_tool_registry

        tool_registry = get_tool_registry()
        logger.info(f"Tool registry initialized with {len(tool_registry.get_tool_names())} tools")

        # 3. 初始化记忆管理器
        from app.memory.unified_memory_manager import UnifiedMemoryManager

        milvus_config = config_data.get("milvus", {})
        memory_config = config_data.get("memory", {})
        embedding_config = config_data.get("embedding", {})

        app.state.memory_manager = UnifiedMemoryManager(
            milvus_host=os.getenv("MILVUS_HOST", milvus_config.get("host", "localhost")),
            milvus_port=int(os.getenv("MILVUS_PORT", milvus_config.get("port", 19530))),
            embedding_service_url=os.getenv(
                "EMBEDDING_SERVICE_URL",
                embedding_config.get("service_url", "http://localhost:8002"),
            ),
            collection_name=os.getenv(
                "MEMORY_COLLECTION", memory_config.get("collection_name", "agent_memory")
            ),
            time_decay_half_life_days=int(
                os.getenv(
                    "MEMORY_HALF_LIFE_DAYS",
                    memory_config.get("time_decay_half_life_days", 30),
                )
            ),
            auto_save_to_long_term=os.getenv(
                "AUTO_SAVE_LONG_TERM", str(memory_config.get("auto_save_to_long_term", True))
            ).lower()
            == "true",
            long_term_importance_threshold=float(
                os.getenv(
                    "IMPORTANCE_THRESHOLD",
                    memory_config.get("long_term_importance_threshold", 0.6),
                )
            ),
        )

        logger.info("Memory manager initialized")

        # 4. 初始化任务管理器
        from app.services.task_manager import task_manager

        await task_manager.initialize()
        logger.info("Task manager initialized with Redis persistence")
        app.state.task_manager = task_manager

        # 5. 设置记忆管理器到路由
        from app.routers import memory as memory_router

        memory_router.set_memory_manager(app.state.memory_manager)

        # 6. 初始化 Agent 引擎
        from app.core.agent_engine import AgentEngine

        app.state.agent_engine = AgentEngine()
        await app.state.agent_engine.initialize()

        logger.info("Agent Engine started successfully")

        yield

    finally:
        logger.info("Shutting down Agent Engine...")

        # 清理资源
        if hasattr(app.state, "task_manager"):
            await app.state.task_manager.close()

        if hasattr(app.state, "agent_engine"):
            await app.state.agent_engine.cleanup()

        # 关闭配置管理器
        if hasattr(app.state, "config_manager") and app.state.config_manager:
            app.state.config_manager.close()

        logger.info("Agent Engine shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Agent Engine",
    description="智能代理引擎 - LangGraph 工作流、ReAct、工具调用、记忆管理",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（使用统一配置）
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# 限流中间件
rate_limit_config = {
    "max_requests": int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100")),
    "window_seconds": int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
}
app.add_middleware(RateLimitMiddleware, **rate_limit_config)

# 幂等性中间件
app.add_middleware(
    IdempotencyMiddleware, ttl_seconds=int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "300"))
)

# 日志中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# 成本追踪中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# Metrics 中间件
app.add_middleware(MetricsMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
app.include_router(memory_router.router)
app.include_router(tools_router.router)
app.include_router(executor_router.router)
app.include_router(llm_router.router)
app.include_router(websocket_router.router)
app.include_router(permissions_router.router)

# Iteration 2 新增路由
app.include_router(self_rag_router.router)
app.include_router(smart_memory_router.router)
app.include_router(multi_agent_router.router)

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 静态文件（WebSocket 测试页面）
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== 健康检查 ====================


@app.get("/health", response_model=HealthResponse, tags=["Health"], summary="健康检查")
async def health_check():
    """基础健康检查"""
    return HealthResponse(status="healthy", service="agent-engine")


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"], summary="就绪检查")
async def readiness_check(agent_engine=Depends(get_agent_engine)):
    """详细就绪检查"""
    checks = ReadinessCheck(
        engine=agent_engine is not None,
        llm=agent_engine.llm_client is not None if agent_engine else False,
        tools=agent_engine.tool_registry is not None if agent_engine else False,
        memory=agent_engine.memory_manager is not None if agent_engine else False,
    )

    all_ready = all([checks.engine, checks.llm, checks.tools, checks.memory])

    return ReadinessResponse(ready=all_ready, checks=checks)


@app.get(
    "/config/info", response_model=ConfigInfoResponse, tags=["Configuration"], summary="配置信息"
)
async def config_info(config_manager=Depends(get_config_manager)):
    """获取配置信息（用于调试）"""
    if config_manager:
        return ConfigInfoResponse(
            mode=config_manager.get_mode().value,
            service=config_manager.get("service.name", "unknown"),
            nacos_enabled=True,
        )
    else:
        return ConfigInfoResponse(
            mode="environment",
            service="agent-engine",
            nacos_enabled=False,
        )


# ==================== 任务执行 ====================


@app.post(
    "/execute",
    response_model=ExecuteTaskResponse,
    tags=["Agent Execution"],
    summary="执行 Agent 任务（非流式）",
    description="""
    执行 Agent 任务并返回完整结果

    **执行模式**:
    - `react`: ReAct 模式（推理+行动）
    - `plan_execute`: 计划-执行模式
    - `reflexion`: 反思模式
    - `simple`: 简单模式

    **认证**: 需要有效的 Bearer Token
    **权限**: 需要 `agent:execute` 权限
    """,
)
async def execute_task(
    request: ExecuteTaskRequest,
    agent_engine=Depends(get_agent_engine),
    user: dict = Depends(verify_token),
    _: None = Depends(check_permissions(["agent:execute"])),
    _request_id: str = Depends(get_request_id),
    tenant_id: str | None = Depends(get_tenant_id),
):
    """执行 Agent 任务（非流式）"""
    import time

    start_time = time.time()

    try:
        # 使用请求中的 tenant_id 或从用户信息中获取
        effective_tenant_id = request.tenant_id or tenant_id or user.get("tenant_id")

        result = await agent_engine.execute(
            task=request.task,
            mode=request.mode,
            max_steps=request.max_steps,
            tools=request.tools,
            conversation_id=request.conversation_id,
            tenant_id=effective_tenant_id,
        )

        # 更新指标
        task_counter.labels(
            mode=request.mode, status="success", tenant_id=effective_tenant_id or "unknown"
        ).inc()
        task_duration.labels(mode=request.mode, tenant_id=effective_tenant_id or "unknown").observe(
            time.time() - start_time
        )

        return ExecuteTaskResponse(**result)

    except Exception as e:
        task_counter.labels(
            mode=request.mode, status="error", tenant_id=request.tenant_id or "unknown"
        ).inc()
        logger.error(f"Error executing task: {e}", exc_info=True)
        raise


@app.post(
    "/execute/stream",
    tags=["Agent Execution"],
    summary="执行 Agent 任务（流式）",
    description="流式执行 Agent 任务，实时返回执行进度",
)
async def execute_task_stream(
    request: ExecuteTaskStreamRequest,
    agent_engine=Depends(get_agent_engine),
    user: dict = Depends(verify_token),
    _: None = Depends(check_permissions(["agent:execute"])),
    tenant_id: str | None = Depends(get_tenant_id),
):
    """执行 Agent 任务（流式）"""
    effective_tenant_id = request.tenant_id or tenant_id or user.get("tenant_id")

    try:
        # 创建流式生成器
        async def event_generator():
            async for chunk in agent_engine.execute_stream(
                task=request.task,
                mode=request.mode,
                max_steps=request.max_steps,
                tools=request.tools,
                conversation_id=request.conversation_id,
                tenant_id=effective_tenant_id,
            ):
                yield f"data: {chunk}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.error(f"Error in streaming execution: {e}", exc_info=True)
        raise


# ==================== 工具管理 ====================


@app.get("/tools", response_model=ListToolsResponse, tags=["Tools"], summary="列出所有可用工具")
async def list_tools(
    tool_registry=Depends(get_tool_registry),
    category: str | None = Query(None, description="按分类过滤"),
):
    """列出所有可用工具"""
    tools = tool_registry.list_tools()

    # 按分类过滤
    if category:
        tools = [t for t in tools if t.get("category") == category]

    return ListToolsResponse(tools=tools, count=len(tools))


@app.post(
    "/tools/register",
    response_model=RegisterToolResponse,
    tags=["Tools"],
    summary="动态注册工具",
    description="""
    动态注册自定义工具

    **安全限制**:
    - 只能注册白名单模块中的工具
    - 需要 `tool:register` 权限
    - 工具名称必须唯一
    """,
)
async def register_tool(
    request: RegisterToolRequest,
    tool_registry=Depends(get_tool_registry),
    user: dict = Depends(verify_token),
    _: None = Depends(check_permissions(["tool:register"])),
):
    """动态注册工具"""
    import asyncio
    import importlib
    import inspect

    # 白名单验证
    ALLOWED_TOOL_MODULES = [
        "app.tools.builtin",
        "app.tools.custom",
        "plugins.approved",
    ]

    def resolve_callable(path: str):
        """解析可调用对象（带白名单检查）"""
        if ":" in path:
            module_path, attr_name = path.split(":", 1)
        elif "." in path:
            module_path, attr_name = path.rsplit(".", 1)
        else:
            raise ToolRegistrationError("Callable path must be 'module:attr' or 'module.attr'")

        # 白名单检查
        if not any(module_path.startswith(allowed) for allowed in ALLOWED_TOOL_MODULES):
            raise ToolRegistrationError(
                f"Module '{module_path}' not in allowed list. "
                f"Allowed modules: {', '.join(ALLOWED_TOOL_MODULES)}"
            )

        try:
            module = importlib.import_module(module_path)
            target = getattr(module, attr_name)
        except (ImportError, AttributeError) as e:
            raise ToolRegistrationError(f"Failed to import '{path}': {e}") from e

        if inspect.isclass(target):
            return target

        if callable(target):
            return target

        raise ToolRegistrationError(f"Resolved target '{attr_name}' is not callable")

    # 检查工具是否已存在
    if request.name in tool_registry.get_tool_names():
        raise ToolRegistrationError(f"Tool '{request.name}' already exists")

    # 解析函数
    try:
        target = resolve_callable(request.function.strip())
    except Exception as exc:
        raise ToolRegistrationError(f"Invalid function reference: {exc}") from exc

    # 创建工具实例
    class APIDynamicTool:
        """适配任意可调用对象到动态工具注册表"""

        def __init__(self, tool_name, tool_description, schema, callable_obj, args, kwargs):
            self._definition = {
                "name": tool_name,
                "description": tool_description,
                "parameters": schema,
            }
            self._callable = callable_obj
            self._args = args
            self._kwargs = kwargs

        def get_definition(self):
            return self._definition

        async def execute(self, **kwargs):
            if inspect.isclass(self._callable):
                instance = self._callable(*self._args, **self._kwargs)
                if not hasattr(instance, "execute"):
                    raise ValueError("Tool class must define an 'execute' method")
                execute_method = instance.execute
                if inspect.iscoroutinefunction(execute_method):
                    return await execute_method(**kwargs)
                return await asyncio.to_thread(execute_method, **kwargs)

            call_kwargs = {**self._kwargs, **kwargs}
            if inspect.iscoroutinefunction(self._callable):
                return await self._callable(*self._args, **call_kwargs)

            return await asyncio.to_thread(self._callable, *self._args, **call_kwargs)

    tool_instance = APIDynamicTool(
        tool_name=request.name.strip(),
        tool_description=request.description.strip(),
        schema=request.parameters,
        callable_obj=target,
        args=request.init_args,
        kwargs=request.init_kwargs,
    )

    try:
        tool_registry.register(tool_instance)
    except Exception as exc:
        raise ToolRegistrationError(f"Failed to register tool: {exc}") from exc

    definition = tool_instance.get_definition()
    logger.info(
        f"Successfully registered tool '{definition['name']}' by user {user.get('user_id')}"
    )

    return RegisterToolResponse(
        status="registered",
        tool=definition,
        total=len(tool_registry.get_tool_names()),
    )


@app.delete(
    "/tools/{tool_name}", response_model=UnregisterToolResponse, tags=["Tools"], summary="注销工具"
)
async def unregister_tool(
    tool_name: str,
    _tool_registry=Depends(get_tool_registry),
    user: dict = Depends(verify_token),
    _: None = Depends(check_permissions(["tool:unregister"])),
):
    """注销工具"""
    from app.tools.dynamic_registry import get_tool_registry as get_dynamic_registry

    dynamic_registry = get_dynamic_registry()

    if tool_name not in dynamic_registry.get_tool_names():
        raise ToolNotFoundError(tool_name)

    dynamic_registry.unregister(tool_name)
    logger.info(f"Successfully unregistered tool '{tool_name}' by user {user.get('user_id')}")

    return UnregisterToolResponse(
        message=f"Tool '{tool_name}' unregistered successfully",
        tool_name=tool_name,
    )


# ==================== 统计信息 ====================


@app.get("/stats", response_model=StatsResponse, tags=["Statistics"], summary="获取统计信息")
async def get_stats(
    agent_engine=Depends(get_agent_engine),
    _user: dict | None = Depends(optional_verify_token),
):
    """获取统计信息"""
    stats = await agent_engine.get_stats()
    return StatsResponse(**stats)


if __name__ == "__main__":
    import uvicorn

    # 从环境变量或配置获取参数
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8010"))
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port} with {workers} workers")

    uvicorn.run(
        "main_refactored:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )
