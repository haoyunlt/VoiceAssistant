"""RAG主路由"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.rag import RAGRequest, RAGResponse
from app.services.rag_service import RAGService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
rag_service = RAGService()


@router.post("/generate", response_model=RAGResponse)
async def generate_answer(request: RAGRequest):
    """
    RAG生成答案

    完整的RAG流程：
    1. 查询理解和扩展
    2. 向量检索
    3. 重排序（可选）
    4. 上下文组装
    5. LLM生成
    6. 引用提取
    """
    try:
        logger.info(f"RAG request: query={request.query[:100]}, kb={request.knowledge_base_id}")

        if request.stream:
            # 流式响应
            return StreamingResponse(
                rag_service.generate_stream(request),
                media_type="text/event-stream",
            )
        else:
            # 普通响应
            response = await rag_service.generate(request)
            return response

    except Exception as e:
        logger.error(f"RAG generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve")
async def retrieve_only(request: RAGRequest):
    """
    仅检索（不生成）

    返回相关文档片段，不调用LLM生成
    """
    try:
        logger.info(f"Retrieve request: query={request.query[:100]}")

        documents = await rag_service.retrieve(request)

        return {
            "query": request.query,
            "documents": documents,
            "count": len(documents),
        }

    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
