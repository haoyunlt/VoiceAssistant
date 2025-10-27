"""响应模型"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatChoice(BaseModel):
    """聊天选项"""
    index: int
    message: Dict[str, str]
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str
    model: str
    provider: str
    choices: List[ChatChoice]
    usage: Usage
    created: int


class CompletionChoice(BaseModel):
    """补全选项"""
    index: int
    text: str
    finish_reason: Optional[str] = None


class CompletionResponse(BaseModel):
    """补全响应"""
    id: str
    model: str
    provider: str
    choices: List[CompletionChoice]
    usage: Usage
    created: int


class EmbeddingData(BaseModel):
    """嵌入数据"""
    index: int
    embedding: List[float]
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    """向量化响应"""
    model: str
    provider: str
    data: List[EmbeddingData]
    usage: Usage
