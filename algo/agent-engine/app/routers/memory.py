"""
记忆管理 API 路由
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])


# 请求模型
class StoreMemoryRequest(BaseModel):
    """存储记忆请求"""

    user_id: str = Field(..., description="用户 ID")
    content: str = Field(..., description="记忆内容", min_length=1, max_length=2000)
    memory_type: str = Field(
        default="conversation", description="记忆类型 (conversation/important/note)"
    )
    importance: Optional[float] = Field(
        None, description="重要性 (0.0-1.0)，如果为 None 则自动评估", ge=0.0, le=1.0
    )


class RecallMemoryRequest(BaseModel):
    """回忆记忆请求"""

    user_id: str = Field(..., description="用户 ID")
    query: str = Field(..., description="查询内容", min_length=1)
    conversation_id: Optional[str] = Field(None, description="对话 ID（用于短期记忆）")
    top_k: int = Field(default=5, description="返回数量", ge=1, le=20)
    include_short_term: bool = Field(default=True, description="是否包含短期记忆")
    include_long_term: bool = Field(default=True, description="是否包含长期记忆")


class AddMemoryRequest(BaseModel):
    """添加记忆请求"""

    user_id: str = Field(..., description="用户 ID")
    conversation_id: str = Field(..., description="对话 ID")
    content: str = Field(..., description="内容", min_length=1, max_length=2000)
    role: str = Field(default="user", description="角色 (user/assistant/system)")
    metadata: Optional[dict] = Field(None, description="元数据")


# 响应模型
class StoreMemoryResponse(BaseModel):
    """存储记忆响应"""

    memory_id: str = Field(..., description="记忆 ID")
    importance: float = Field(..., description="重要性评分")
    message: str = Field(default="Memory stored successfully")


class MemoryItem(BaseModel):
    """记忆项"""

    type: str = Field(..., description="记忆类型 (short_term/long_term)")
    content: str = Field(..., description="内容")
    score: float = Field(..., description="相关性得分")
    memory_id: Optional[str] = Field(None, description="记忆 ID（长期记忆）")
    importance: Optional[float] = Field(None, description="重要性（长期记忆）")
    days_ago: Optional[float] = Field(None, description="天数（长期记忆）")
    access_count: Optional[int] = Field(None, description="访问次数（长期记忆）")
    role: Optional[str] = Field(None, description="角色（短期记忆）")


class RecallMemoryResponse(BaseModel):
    """回忆记忆响应"""

    short_term: List[MemoryItem] = Field(default=[], description="短期记忆")
    long_term: List[MemoryItem] = Field(default=[], description="长期记忆")
    combined: List[MemoryItem] = Field(default=[], description="融合后的记忆")
    total_count: int = Field(..., description="总数量")


class MemoryListItem(BaseModel):
    """记忆列表项"""

    memory_id: str = Field(..., description="记忆 ID")
    content: str = Field(..., description="内容")
    memory_type: str = Field(..., description="记忆类型")
    importance: float = Field(..., description="重要性")
    created_at: int = Field(..., description="创建时间戳")
    access_count: int = Field(..., description="访问次数")
    days_ago: float = Field(..., description="天数")


class ListMemoriesResponse(BaseModel):
    """列表记忆响应"""

    memories: List[MemoryListItem] = Field(..., description="记忆列表")
    total: int = Field(..., description="总数量")
    limit: int = Field(..., description="每页数量")
    offset: int = Field(..., description="偏移量")


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""

    short_term: dict = Field(..., description="短期记忆统计")
    long_term: dict = Field(..., description="长期记忆统计")
    config: dict = Field(..., description="配置信息")


# 全局记忆管理器（在 main.py 中初始化）
memory_manager = None


def set_memory_manager(manager):
    """设置记忆管理器"""
    global memory_manager
    memory_manager = manager
    logger.info("Memory manager set in router")


# API 端点
@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(request: StoreMemoryRequest):
    """
    存储记忆到长期记忆

    自动评估重要性并存储到 Milvus 向量数据库
    """
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        memory_id = await memory_manager.store_important_memory(
            user_id=request.user_id,
            content=request.content,
            memory_type=request.memory_type,
            importance=request.importance,
        )

        # 获取实际的重要性评分
        importance = request.importance
        if importance is None:
            importance = await memory_manager.long_term._evaluate_importance(
                request.content
            )

        return StoreMemoryResponse(memory_id=memory_id, importance=importance)

    except Exception as e:
        logger.error(f"Failed to store memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")


@router.post("/recall", response_model=RecallMemoryResponse)
async def recall_memory(request: RecallMemoryRequest):
    """
    回忆相关记忆

    根据查询内容检索相关的短期和长期记忆，自动应用 Ebbinghaus 遗忘曲线衰减
    """
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        result = await memory_manager.recall_memories(
            user_id=request.user_id,
            query=request.query,
            conversation_id=request.conversation_id,
            top_k=request.top_k,
            include_short_term=request.include_short_term,
            include_long_term=request.include_long_term,
        )

        # 转换为响应格式
        short_term = [MemoryItem(**mem) for mem in result["short_term"]]
        long_term = [MemoryItem(**mem) for mem in result["long_term"]]
        combined = [MemoryItem(**mem) for mem in result["combined"]]

        return RecallMemoryResponse(
            short_term=short_term,
            long_term=long_term,
            combined=combined,
            total_count=len(combined),
        )

    except Exception as e:
        logger.error(f"Failed to recall memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recall memory: {str(e)}")


@router.post("/add")
async def add_memory(request: AddMemoryRequest):
    """
    添加记忆（自动分配到短期或长期）

    根据内容重要性自动决定是否保存到长期记忆
    """
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        memory_id = await memory_manager.add_memory(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            content=request.content,
            role=request.role,
            metadata=request.metadata,
        )

        if memory_id:
            return {
                "message": "Memory added to both short-term and long-term",
                "memory_id": memory_id,
                "stored_in_long_term": True,
            }
        else:
            return {
                "message": "Memory added to short-term only",
                "memory_id": None,
                "stored_in_long_term": False,
            }

    except Exception as e:
        logger.error(f"Failed to add memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add memory: {str(e)}")


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """删除长期记忆"""
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        await memory_manager.delete_memory(memory_id)

        return {"message": "Memory deleted successfully", "memory_id": memory_id}

    except Exception as e:
        logger.error(f"Failed to delete memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")


@router.get("/list/{user_id}", response_model=ListMemoriesResponse)
async def list_user_memories(
    user_id: str, limit: int = 20, offset: int = 0
):
    """列出用户的所有长期记忆"""
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        memories = await memory_manager.list_user_memories(
            user_id=user_id, limit=limit, offset=offset
        )

        memory_items = [MemoryListItem(**mem) for mem in memories]

        return ListMemoriesResponse(
            memories=memory_items, total=len(memory_items), limit=limit, offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {str(e)}")


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """获取记忆系统统计信息"""
    if not memory_manager:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")

    try:
        stats = memory_manager.get_stats()

        return MemoryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

