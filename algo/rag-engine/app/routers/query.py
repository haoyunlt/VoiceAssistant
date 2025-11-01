"""查询理解路由"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.query_service import QueryService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
query_service = QueryService()


class QueryExpansionRequest(BaseModel):
    """查询扩展请求"""

    query: str = Field(..., description="原始查询")
    num_expansions: int = Field(default=3, description="扩展查询数量")


@router.post("/expand")
async def expand_query(request: QueryExpansionRequest):
    """
    查询扩展

    使用LLM生成查询的多个变体，提高召回率
    """
    try:
        result = await query_service.expand_query(
            request.query,
            num_expansions=request.num_expansions,
        )

        return result

    except Exception as e:
        logger.error(f"Query expansion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/extract-keywords")
async def extract_keywords(query: str):
    """
    提取关键词

    从查询中提取关键词和实体
    """
    try:
        keywords = await query_service.extract_keywords(query)

        return {
            "query": query,
            "keywords": keywords,
        }

    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
