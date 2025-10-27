"""Model Adapter服务 - 统一的LLM提供商适配层."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import make_asgi_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Model Adapter Service...")

    # 初始化适配器
    from app.adapters.claude_adapter import ClaudeAdapter
    from app.adapters.openai_adapter import OpenAIAdapter
    from app.adapters.zhipu_adapter import ZhipuAdapter

    global adapters

    adapters = {}

    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        adapters["openai"] = OpenAIAdapter(openai_key)
        logger.info("OpenAI adapter initialized")

    # Claude
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    if claude_key:
        adapters["claude"] = ClaudeAdapter(claude_key)
        logger.info("Claude adapter initialized")

    # Zhipu
    zhipu_key = os.getenv("ZHIPU_API_KEY")
    if zhipu_key:
        adapters["zhipu"] = ZhipuAdapter(zhipu_key)
        logger.info("Zhipu adapter initialized")

    logger.info(f"Model Adapter Service started with {len(adapters)} providers")

    yield

    # 清理资源
    logger.info("Shutting down Model Adapter Service...")

    for provider, adapter in adapters.items():
        if hasattr(adapter, "close"):
            try:
                await adapter.close()
            except Exception as e:
                logger.error(f"Error closing {provider} adapter: {e}")

    logger.info("Model Adapter Service shut down complete")


# 创建FastAPI应用
app = FastAPI(
    title="Model Adapter",
    description="统一的LLM提供商适配层 - OpenAI/Claude/Zhipu",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 全局适配器字典
adapters = {}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "model-adapter",
        "providers": list(adapters.keys()),
    }


@app.get("/api/v1/providers")
async def list_providers():
    """列出可用的提供商"""
    provider_status = {}

    for provider, adapter in adapters.items():
        try:
            is_healthy = await adapter.health_check()
            provider_status[provider] = {
                "available": True,
                "healthy": is_healthy,
            }
        except Exception as e:
            provider_status[provider] = {
                "available": True,
                "healthy": False,
                "error": str(e),
            }

    return {
        "providers": provider_status,
        "count": len(adapters),
    }


@app.post("/api/v1/generate")
async def generate(request: dict):
    """
    生成文本 (非流式).

    Args:
        provider: 提供商 (openai/claude/zhipu)
        model: 模型名称
        messages: 消息列表
        temperature: 温度
        max_tokens: 最大token数
        ...其他参数
    """
    provider = request.get("provider")
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required")

    adapter = adapters.get(provider)
    if not adapter:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not found"
        )

    try:
        response = await adapter.generate(
            model=request.get("model"),
            messages=request.get("messages", []),
            temperature=request.get("temperature", 0.7),
            max_tokens=request.get("max_tokens", 1000),
        )

        return {
            "provider": response.provider,
            "model": response.model,
            "content": response.content,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
            "metadata": response.metadata,
        }

    except Exception as e:
        logger.error(f"Generation failed for {provider}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/stream")
async def generate_stream(request: dict):
    """
    生成文本 (流式).

    使用Server-Sent Events (SSE)格式返回。
    """
    provider = request.get("provider")
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required")

    adapter = adapters.get(provider)
    if not adapter:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not found"
        )

    async def event_stream():
        """SSE事件流"""
        try:
            async for chunk in adapter.generate_stream(
                model=request.get("model"),
                messages=request.get("messages", []),
                temperature=request.get("temperature", 0.7),
                max_tokens=request.get("max_tokens", 1000),
            ):
                import json

                data = json.dumps(
                    {
                        "provider": chunk.provider,
                        "model": chunk.model,
                        "content": chunk.content,
                        "finish_reason": chunk.finish_reason,
                    },
                    ensure_ascii=False,
                )
                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed for {provider}: {e}", exc_info=True)
            import json

            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/v1/embeddings")
async def create_embeddings(request: dict):
    """
    创建文本嵌入.

    Args:
        provider: 提供商 (openai/zhipu)
        model: 嵌入模型
        input: 输入文本或文本列表
    """
    provider = request.get("provider")
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required")

    adapter = adapters.get(provider)
    if not adapter:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not found"
        )

    if not hasattr(adapter, "create_embedding"):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' does not support embeddings",
        )

    try:
        result = await adapter.create_embedding(
            model=request.get("model"),
            input_text=request.get("input"),
        )

        return result

    except Exception as e:
        logger.error(f"Embedding failed for {provider}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/convert")
async def convert_protocol(request: dict):
    """
    协议转换.

    将统一格式转换为特定Provider格式。
    """
    from app.core.protocol_converter import ProtocolConverter

    target_provider = request.get("target_provider")
    messages = request.get("messages", [])
    parameters = request.get("parameters", {})

    if target_provider == "openai":
        result = ProtocolConverter.to_openai_format(messages, parameters)
    elif target_provider == "claude":
        result = ProtocolConverter.to_claude_format(messages, parameters)
    elif target_provider == "zhipu":
        result = ProtocolConverter.to_zhipu_format(messages, parameters)
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown provider: {target_provider}"
        )

    return result


@app.post("/api/v1/cost/calculate")
async def calculate_cost(request: dict):
    """
    计算成本.

    Args:
        model: 模型名称
        input_tokens: 输入token数
        output_tokens: 输出token数
    """
    from app.core.cost_calculator import CostCalculator

    model = request.get("model")
    input_tokens = request.get("input_tokens", 0)
    output_tokens = request.get("output_tokens", 0)

    if not model:
        raise HTTPException(status_code=400, detail="Model is required")

    cost = CostCalculator.calculate_cost(model, input_tokens, output_tokens)

    return cost


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8005"))
    workers = int(os.getenv("WORKERS", "1"))

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
    )
