import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from app.adapters.azure_adapter import AzureAdapter
from app.adapters.claude_adapter import ClaudeAdapter
from app.adapters.openai_adapter import OpenAIAdapter
from app.core.adapter_registry import AdapterRegistry
from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from prometheus_client import Counter, Histogram, make_asgi_app

# 配置日志
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    "model_adapter_requests_total", "Total number of Model Adapter requests", ["provider", "model"]
)
REQUEST_LATENCY = Histogram(
    "model_adapter_request_duration_seconds", "Model Adapter request latency in seconds", ["provider", "model"]
)

adapter_registry: AdapterRegistry = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global adapter_registry

    logger.info("Starting Model Adapter service...")

    try:
        # 初始化适配器注册表
        adapter_registry = AdapterRegistry()

        # 注册各个适配器
        openai_adapter = OpenAIAdapter()
        claude_adapter = ClaudeAdapter()
        azure_adapter = AzureAdapter()

        adapter_registry.register("openai", openai_adapter)
        adapter_registry.register("anthropic", claude_adapter)
        adapter_registry.register("azure", azure_adapter)

        logger.info(f"Registered adapters: {adapter_registry.list_adapters()}")

        logger.info("Model Adapter service started successfully.")

        # OpenTelemetry Instrumentation
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        yield

    finally:
        logger.info("Shutting down Model Adapter service...")
        if adapter_registry:
            await adapter_registry.cleanup()
        logger.info("Model Adapter service shut down complete.")

app = FastAPI(
    title="Model Adapter Service",
    version="1.0.0",
    description="LLM Model Adapter for VoiceHelper - API 适配与协议转换",
    lifespan=lifespan,
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.get("/")
async def read_root():
    return {"message": "Model Adapter Service is running!"}

@app.get("/health")
async def health_check():
    """健康检查"""
    global adapter_registry
    if adapter_registry:
        return {"status": "ok"}
    raise HTTPException(status_code=503, detail="Model Adapter not ready")

@app.post("/chat/completions")
async def chat_completions(
    provider: str,
    model: str,
    messages: list[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
    tenant_id: str = None,
    user_id: str = None,
):
    """
    统一的聊天补全接口，自动路由到对应的模型提供商。

    Args:
        provider: 模型提供商 (openai, anthropic, azure)
        model: 模型名称
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大 token 数
        stream: 是否流式响应
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    global adapter_registry
    if not adapter_registry:
        raise HTTPException(status_code=503, detail="Model Adapter not initialized")

    REQUEST_COUNT.labels(provider=provider, model=model).inc()

    try:
        with REQUEST_LATENCY.labels(provider=provider, model=model).time():
            adapter = adapter_registry.get_adapter(provider)

            if stream:
                # TODO: Implement streaming response
                raise NotImplementedError("Streaming is not yet implemented.")
            else:
                response = await adapter.chat_completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                return response
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except Exception as e:
        logger.error(f"Error in chat completion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings")
async def embeddings(
    provider: str,
    model: str,
    input: str | list[str],
    tenant_id: str = None,
    user_id: str = None,
):
    """
    统一的嵌入接口。
    """
    global adapter_registry
    if not adapter_registry:
        raise HTTPException(status_code=503, detail="Model Adapter not initialized")

    try:
        adapter = adapter_registry.get_adapter(provider)
        response = await adapter.embeddings(
            model=model,
            input=input,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return response
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except Exception as e:
        logger.error(f"Error in embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/adapters")
async def list_adapters():
    """列出所有已注册的适配器"""
    global adapter_registry
    if not adapter_registry:
        raise HTTPException(status_code=503, detail="Model Adapter not initialized")
    return {"adapters": adapter_registry.list_adapters()}

@app.get("/stats")
async def get_stats():
    """获取 Model Adapter 统计信息"""
    global adapter_registry
    if not adapter_registry:
        raise HTTPException(status_code=503, detail="Model Adapter not initialized")
    return await adapter_registry.get_stats()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting Model Adapter server on {host}:{port} with {workers} workers")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )
