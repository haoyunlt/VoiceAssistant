"""错误处理中间件 - 统一异常处理"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.exceptions import (
    BackendNotAvailableException,
    BackendNotInitializedException,
    CollectionNotFoundException,
    DeleteFailedException,
    InsertFailedException,
    InvalidVectorDimensionException,
    SearchFailedException,
    VectorStoreException,
)

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """统一错误处理中间件"""
    try:
        return await call_next(request)
    except Exception as exc:
        return handle_exception(request, exc)


def handle_exception(request: Request, exc: Exception) -> JSONResponse:
    """处理异常并返回 JSON 响应"""
    trace_id = getattr(request.state, "trace_id", "unknown")

    # Pydantic 验证错误
    if isinstance(exc, ValidationError):
        logger.warning(
            f"Validation error: {exc}",
            extra={"trace_id": trace_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
                "trace_id": trace_id,
            },
        )

    # 后端不可用
    if isinstance(exc, BackendNotAvailableException):
        logger.error(
            f"Backend not available: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "backend_not_available",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 后端未初始化
    if isinstance(exc, BackendNotInitializedException):
        logger.error(
            f"Backend not initialized: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "backend_not_initialized",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 集合不存在
    if isinstance(exc, CollectionNotFoundException):
        logger.warning(
            f"Collection not found: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "collection_not_found",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 向量维度无效
    if isinstance(exc, InvalidVectorDimensionException):
        logger.warning(
            f"Invalid vector dimension: {exc.message}",
            extra={"trace_id": trace_id},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_vector_dimension",
                "message": exc.message,
                "trace_id": trace_id,
            },
        )

    # 插入失败
    if isinstance(exc, InsertFailedException):
        logger.error(
            f"Insert failed: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "insert_failed",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 搜索失败
    if isinstance(exc, SearchFailedException):
        logger.error(
            f"Search failed: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "search_failed",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 删除失败
    if isinstance(exc, DeleteFailedException):
        logger.error(
            f"Delete failed: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "delete_failed",
                "message": exc.message,
                "backend": exc.backend,
                "trace_id": trace_id,
            },
        )

    # 其他向量存储异常
    if isinstance(exc, VectorStoreException):
        logger.error(
            f"Vector store error: {exc.message}",
            extra={"trace_id": trace_id, "backend": exc.backend},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "vector_store_error",
                "message": exc.message,
                "backend": exc.backend,
                "details": exc.details,
                "trace_id": trace_id,
            },
        )

    # 未知错误
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={"trace_id": trace_id, "path": request.url.path},
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "trace_id": trace_id,
        },
    )
