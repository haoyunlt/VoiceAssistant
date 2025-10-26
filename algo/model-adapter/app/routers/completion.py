"""补全接口路由"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.request import CompletionRequest
from app.models.response import CompletionResponse
from app.services.adapter_service import AdapterService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
adapter_service = AdapterService()


@router.post("/create", response_model=CompletionResponse)
async def create_completion(request: CompletionRequest):
    """
    创建文本补全

    支持多个模型提供商的文本补全功能
    """
    try:
        logger.info(f"Completion request: model={request.model}, provider={request.provider}")

        if request.stream:
            # 流式响应
            return StreamingResponse(
                adapter_service.completion_stream(request),
                media_type="text/event-stream",
            )
        else:
            # 普通响应
            response = await adapter_service.completion(request)
            return response

    except Exception as e:
        logger.error(f"Completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
