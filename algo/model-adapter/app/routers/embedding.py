"""向量化接口路由"""
import logging

from fastapi import APIRouter, HTTPException

from app.models.request import EmbeddingRequest
from app.models.response import EmbeddingResponse
from app.services.adapter_service import AdapterService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
adapter_service = AdapterService()


@router.post("/create", response_model=EmbeddingResponse)
async def create_embedding(request: EmbeddingRequest):
    """
    创建文本向量

    支持多个模型提供商的文本向量化功能：
    - OpenAI (text-embedding-3-small, text-embedding-3-large)
    - Azure OpenAI
    - 智谱AI
    - 通义千问
    """
    try:
        logger.info(
            f"Embedding request: model={request.model}, "
            f"texts={len(request.input)}, provider={request.provider}"
        )

        response = await adapter_service.embedding(request)
        return response

    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
