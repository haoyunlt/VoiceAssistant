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

# 尝试导入 Nacos 配置（可选）
try:
    from nacos_config import get_config_manager, init_config
    NACOS_AVAILABLE = True
except ImportError:
    NACOS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Nacos support not available, using environment variables only")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics 中间件
app.add_middleware(MetricsMiddleware)

# 注册路由
from app.routers import executor as executor_router
from app.routers import llm as llm_router
from app.routers import memory as memory_router
from app.routers import tools as tools_router
from app.routers import websocket as websocket_router

app.include_router(memory_router.router)
app.include_router(tools_router.router)
app.include_router(executor_router.router)
app.include_router(llm_router.router)
app.include_router(websocket_router.router)

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
    注册新工具

    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数 Schema
        function: 工具函数（暂不支持动态注册）
    """
    global agent_engine

    if not agent_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # TODO: 实现动态工具注册
    raise HTTPException(status_code=501, detail="Dynamic tool registration not yet implemented")


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
