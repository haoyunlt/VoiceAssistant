"""
Agent Engine - 智能代理引擎（支持 Nacos 配置中心）

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

from app.middleware.metrics import MetricsMiddleware
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

# 添加 common 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

# 导入统一基础设施模块
from cors_config import get_cors_config
from cost_tracking import cost_tracking_middleware
from exception_handlers import register_exception_handlers
from structured_logging import logging_middleware, setup_logging
from telemetry import TracingConfig, init_tracing

# 配置统一日志
setup_logging(service_name="agent-engine")
logger = logging.getLogger(__name__)

# 尝试导入 Nacos 配置（可选）
try:
    from nacos_config import get_config_manager, init_config
    NACOS_AVAILABLE = True
except ImportError:
    NACOS_AVAILABLE = False
    logger.warning("Nacos support not available, using environment variables only")

# 全局变量
agent_engine = None
memory_manager = None
config_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent_engine, memory_manager, config_manager

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
            config_manager = get_config_manager()

            logger.info(f"Config mode: {config_manager.get_mode()}")
            logger.info(f"Service name: {config_data.get('service', {}).get('name', service_name)}")
        else:
            logger.info("Using environment variables for configuration")
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

        memory_manager = UnifiedMemoryManager(
            milvus_host=os.getenv("MILVUS_HOST", milvus_config.get("host", "localhost")),
            milvus_port=int(os.getenv("MILVUS_PORT", milvus_config.get("port", 19530))),
            embedding_service_url=os.getenv(
                "EMBEDDING_SERVICE_URL",
                embedding_config.get("service_url", "http://localhost:8002")
            ),
            collection_name=os.getenv(
                "MEMORY_COLLECTION",
                memory_config.get("collection_name", "agent_memory")
            ),
            time_decay_half_life_days=int(os.getenv(
                "MEMORY_HALF_LIFE_DAYS",
                memory_config.get("time_decay_half_life_days", 30)
            )),
            auto_save_to_long_term=os.getenv(
                "AUTO_SAVE_LONG_TERM",
                str(memory_config.get("auto_save_to_long_term", True))
            ).lower() == "true",
            long_term_importance_threshold=float(os.getenv(
                "IMPORTANCE_THRESHOLD",
                memory_config.get("long_term_importance_threshold", 0.6)
            )),
        )

        logger.info("Memory manager initialized")

        # 4. 初始化任务管理器
        from app.services.task_manager import task_manager

        await task_manager.initialize()
        logger.info("Task manager initialized with Redis persistence")

        # 5. 设置记忆管理器到路由
        from app.routers import memory as memory_router

        memory_router.set_memory_manager(memory_manager)

        # 6. 初始化 Agent 引擎
        from app.core.agent_engine import AgentEngine

        agent_engine = AgentEngine()
        await agent_engine.initialize()

        logger.info("Agent Engine started successfully")

        yield

    finally:
        logger.info("Shutting down Agent Engine...")

        # 清理资源
        if task_manager:
            await task_manager.close()

        if agent_engine:
            await agent_engine.cleanup()

        # 关闭配置管理器
        if config_manager:
            config_manager.close()

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

# 日志中间件
from starlette.middleware.base import BaseHTTPMiddleware

app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# 成本追踪中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# Metrics 中间件
app.add_middleware(MetricsMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
from app.routers import executor as executor_router
from app.routers import llm as llm_router
from app.routers import memory as memory_router
from app.routers import permissions as permissions_router
from app.routers import tools as tools_router
from app.routers import websocket as websocket_router

app.include_router(memory_router.router)
app.include_router(tools_router.router)
app.include_router(executor_router.router)
app.include_router(llm_router.router)
app.include_router(websocket_router.router)
app.include_router(permissions_router.router)

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 静态文件（WebSocket 测试页面）
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "agent-engine"}


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    global agent_engine

    checks = {
        "engine": agent_engine is not None,
        "llm": agent_engine.llm_client is not None if agent_engine else False,
        "tools": agent_engine.tool_registry is not None if agent_engine else False,
        "memory": agent_engine.memory_manager is not None if agent_engine else False,
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.get("/config/info")
async def config_info():
    """配置信息（用于调试）"""
    global config_manager

    if config_manager:
        return {
            "mode": config_manager.get_mode().value,
            "service": config_manager.get("service.name", "unknown"),
            "nacos_enabled": True,
        }
    else:
        return {
            "mode": "environment",
            "service": "agent-engine",
            "nacos_enabled": False,
        }


@app.post("/execute")
async def execute_task(request: dict):
    """
    执行 Agent 任务（非流式）

    Args:
        task: 任务描述
        mode: 执行模式 (react/plan_execute/simple)
        max_steps: 最大步骤数
        tools: 可用工具列表
        conversation_id: 会话 ID（用于记忆）
        tenant_id: 租户 ID
    """
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    task = request.get("task")
    if not task:
        raise HTTPException(status_code=400, detail="Task is required")

    try:
        result = await agent_engine.execute(
            task=task,
            mode=request.get("mode", "react"),
            max_steps=request.get("max_steps", 10),
            tools=request.get("tools"),
            conversation_id=request.get("conversation_id"),
            tenant_id=request.get("tenant_id"),
        )

        return result

    except Exception as e:
        logger.error(f"Error executing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute/stream")
async def execute_task_stream(request: dict):
    """
    执行 Agent 任务（流式）

    Args:
        task: 任务描述
        mode: 执行模式
        max_steps: 最大步骤数
        tools: 可用工具列表
        conversation_id: 会话 ID
        tenant_id: 租户 ID
    """
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    task = request.get("task")
    if not task:
        raise HTTPException(status_code=400, detail="Task is required")

    try:
        # 创建流式生成器
        async def event_generator():
            async for chunk in agent_engine.execute_stream(
                task=task,
                mode=request.get("mode", "react"),
                max_steps=request.get("max_steps", 10),
                tools=request.get("tools"),
                conversation_id=request.get("conversation_id"),
                tenant_id=request.get("tenant_id"),
            ):
                yield f"data: {chunk}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.error(f"Error in streaming execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_tools():
    """列出所有可用工具"""
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    tools = agent_engine.tool_registry.list_tools()

    return {
        "tools": tools,
        "count": len(tools),
    }


@app.post("/tools/register")
async def register_tool(request: dict):
    """
    动态注册工具

    请求体格式:
    {
        "name": "custom_tool",
        "description": "自定义工具描述",
        "function": "package.module:callable",
        "parameters": {...},          # OpenAI Function JSON Schema
        "init_args": [],              # 可选，初始化位置参数
        "init_kwargs": {}             # 可选，初始化关键字参数
    }
    """
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    required_fields = ("name", "description", "parameters", "function")
    missing = [field for field in required_fields if not request.get(field)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}",
        )

    name = request["name"]
    description = request["description"]
    parameters = request["parameters"]
    function_path = request["function"]
    init_args = request.get("init_args", [])
    init_kwargs = request.get("init_kwargs", {})

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="Field 'name' must be a non-empty string")

    if not isinstance(description, str) or not description.strip():
        raise HTTPException(status_code=400, detail="Field 'description' must be a non-empty string")

    if not isinstance(parameters, dict):
        raise HTTPException(status_code=400, detail="Field 'parameters' must be an object")

    if not isinstance(function_path, str) or not function_path.strip():
        raise HTTPException(status_code=400, detail="Field 'function' must be a non-empty string")

    if not isinstance(init_args, list):
        raise HTTPException(status_code=400, detail="Field 'init_args' must be a list when provided")

    if not isinstance(init_kwargs, dict):
        raise HTTPException(status_code=400, detail="Field 'init_kwargs' must be an object when provided")

    import asyncio
    import importlib
    import inspect

    def resolve_callable(path: str):
        if ":" in path:
            module_path, attr_name = path.split(":", 1)
        elif "." in path:
            module_path, attr_name = path.rsplit(".", 1)
        else:
            raise ValueError("Callable path must be 'module:attr' or 'module.attr'")

        module = importlib.import_module(module_path)
        target = getattr(module, attr_name)

        if inspect.isclass(target):
            return target

        if callable(target):
            return target

        raise TypeError(f"Resolved target '{attr_name}' is not callable")

    try:
        target = resolve_callable(function_path.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid function reference: {exc}") from exc

    from app.tools.dynamic_registry import get_tool_registry

    registry = get_tool_registry()

    if name in registry.get_tool_names():
        raise HTTPException(status_code=409, detail=f"Tool '{name}' already exists")

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
                execute_method = getattr(instance, "execute")
                if inspect.iscoroutinefunction(execute_method):
                    return await execute_method(**kwargs)
                return await asyncio.to_thread(execute_method, **kwargs)

            call_kwargs = {**self._kwargs, **kwargs}
            if inspect.iscoroutinefunction(self._callable):
                return await self._callable(*self._args, **call_kwargs)

            return await asyncio.to_thread(self._callable, *self._args, **call_kwargs)

    tool_instance = APIDynamicTool(
        tool_name=name.strip(),
        tool_description=description.strip(),
        schema=parameters,
        callable_obj=target,
        args=init_args,
        kwargs=init_kwargs,
    )

    try:
        registry.register(tool_instance)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to register tool: {exc}") from exc

    definition = tool_instance.get_definition()
    logger.info("Successfully registered tool '%s'", definition["name"])

    return {
        "status": "registered",
        "tool": definition,
        "total": len(registry.get_tool_names()),
    }


@app.delete("/tools/{tool_name}")
async def unregister_tool(tool_name: str):
    """
    注销工具

    Args:
        tool_name: 工具名称
    """
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    from app.tools.dynamic_registry import get_tool_registry

    registry = get_tool_registry()

    if tool_name in registry.get_tool_names():
        registry.unregister(tool_name)
        logger.info("Successfully unregistered dynamic tool: %s", tool_name)
        return {
            "message": f"Tool '{tool_name}' unregistered successfully",
            "tool_name": tool_name,
        }

    tool = getattr(agent_engine.tool_registry, "tools", {}).get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    if hasattr(agent_engine.tool_registry, "unregister_tool"):
        agent_engine.tool_registry.unregister_tool(tool_name)
    else:
        agent_engine.tool_registry.tools.pop(tool_name, None)

    logger.info("Successfully unregistered tool: %s", tool_name)

    return {
        "message": f"Tool '{tool_name}' unregistered successfully",
        "tool_name": tool_name,
    }


@app.get("/memory/{conversation_id}")
async def get_memory(conversation_id: str):
    """获取会话记忆"""
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    memory = await agent_engine.memory_manager.get_memory(conversation_id)

    return {
        "conversation_id": conversation_id,
        "memory": memory,
    }


@app.delete("/memory/{conversation_id}")
async def clear_memory(conversation_id: str):
    """清除会话记忆"""
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    await agent_engine.memory_manager.clear_memory(conversation_id)

    return {
        "conversation_id": conversation_id,
        "status": "cleared",
    }


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return await agent_engine.get_stats()


if __name__ == "__main__":
    import uvicorn

    # 从环境变量或配置获取参数
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8003"))
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
