"""聊天接口路由"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.request import ChatRequest
from app.models.response import ChatResponse
from app.services.adapter_service import AdapterService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
adapter_service = AdapterService()


@router.post("/completions", response_model=ChatResponse)
async def create_chat_completion(request: ChatRequest):
    """
    创建聊天补全

    统一的Chat Completion接口，支持多个模型提供商：
    - OpenAI (gpt-4, gpt-3.5-turbo)
    - Azure OpenAI
    - Anthropic (claude-3)
    - 智谱AI (glm-4)
    - 通义千问 (qwen-max)
    - 百度文心 (ernie-bot)
    """
    try:
        logger.info(f"Chat request: model={request.model}, provider={request.provider}")

        if request.stream:
            # 流式响应
            return StreamingResponse(
                adapter_service.chat_stream(request),
                media_type="text/event-stream",
            )
        else:
            # 普通响应
            response = await adapter_service.chat(request)
            return response

    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """
    列出所有支持的模型

    返回各个提供商支持的模型列表
    """
    return {
        "openai": [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "azure-openai": [
            "gpt-4",
            "gpt-35-turbo",
        ],
        "anthropic": [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        "zhipu": [
            "glm-4",
            "glm-3-turbo",
        ],
        "qwen": [
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
        ],
        "baidu": [
            "ERNIE-Bot-4",
            "ERNIE-Bot-turbo",
        ],
    }
