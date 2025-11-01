"""批处理API路由 - 并发处理多个请求."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.adapter_manager import AdapterManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/batch", tags=["batch"])


# 批处理请求模型
class BatchChatRequest(BaseModel):
    """批处理聊天请求."""

    requests: list[dict] = Field(..., description="请求列表")
    max_concurrency: int = Field(default=5, ge=1, le=10, description="最大并发数")


class BatchChatResponse(BaseModel):
    """批处理聊天响应."""

    results: list[dict] = Field(..., description="响应列表")
    total: int = Field(..., description="总请求数")
    success: int = Field(..., description="成功数")
    failed: int = Field(..., description="失败数")
    duration_seconds: float = Field(..., description="总耗时(秒)")


async def process_single_request(
    adapter_manager: AdapterManager,
    request_data: dict,
    index: int,
) -> dict:
    """
    处理单个请求.

    Args:
        adapter_manager: 适配器管理器
        request_data: 请求数据
        index: 请求索引

    Returns:
        处理结果
    """
    try:
        # 提取参数
        provider = request_data.get("provider", "openai")
        model = request_data.get("model", "gpt-3.5-turbo")
        messages = request_data.get("messages", [])

        # 获取适配器
        adapter = adapter_manager.get_adapter(provider)

        # 调用生成
        response = await adapter.generate(
            model=model,
            messages=messages,
            temperature=request_data.get("temperature", 0.7),
            max_tokens=request_data.get("max_tokens", 1000),
        )

        return {
            "index": index,
            "success": True,
            "provider": response.provider,
            "model": response.model,
            "content": response.content,
            "usage": response.usage,
            "metadata": response.metadata,
        }

    except Exception as e:
        logger.error(f"Batch request {index} failed: {e}")
        return {
            "index": index,
            "success": False,
            "error": str(e),
        }


@router.post("/completions", response_model=BatchChatResponse)
async def create_batch_chat_completions(
    request: BatchChatRequest,
    adapter_manager: Annotated[AdapterManager, Depends()],
):
    """
    批量创建聊天补全.

    支持并发处理多个请求，提升吞吐量。

    Args:
        request: 批处理请求
        adapter_manager: 适配器管理器

    Returns:
        批处理响应

    Example:
        ```json
        {
            "requests": [
                {
                    "provider": "openai",
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello"}]
                },
                {
                    "provider": "openai",
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hi"}]
                }
            ],
            "max_concurrency": 5
        }
        ```
    """
    import time

    start_time = time.time()

    # 限制批量大小
    if len(request.requests) > 10:
        raise HTTPException(
            status_code=400,
            detail="Batch size exceeds limit (max 10)",
        )

    logger.info(f"Processing batch: {len(request.requests)} requests, concurrency={request.max_concurrency}")

    # 创建semaphore控制并发
    semaphore = asyncio.Semaphore(request.max_concurrency)

    async def process_with_semaphore(req_data, idx):
        async with semaphore:
            return await process_single_request(adapter_manager, req_data, idx)

    # 并发处理所有请求
    tasks = [
        process_with_semaphore(req_data, i)
        for i, req_data in enumerate(request.requests)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    # 统计结果
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count

    duration = time.time() - start_time

    logger.info(
        f"Batch completed: {success_count} success, {failed_count} failed, "
        f"{duration:.2f}s"
    )

    return BatchChatResponse(
        results=results,
        total=len(results),
        success=success_count,
        failed=failed_count,
        duration_seconds=round(duration, 3),
    )
