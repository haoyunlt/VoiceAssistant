"""响应模型"""

from pydantic import BaseModel


class Usage(BaseModel):
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatChoice(BaseModel):
    """聊天选项"""
    index: int
    message: dict[str, str]
    finish_reason: str | None = None


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str
    model: str
    provider: str
    choices: list[ChatChoice]
    usage: Usage
    created: int


class CompletionChoice(BaseModel):
    """补全选项"""
    index: int
    text: str
    finish_reason: str | None = None


class CompletionResponse(BaseModel):
    """补全响应"""
    id: str
    model: str
    provider: str
    choices: list[CompletionChoice]
    usage: Usage
    created: int


class EmbeddingData(BaseModel):
    """嵌入数据"""
    index: int
    embedding: list[float]
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    """向量化响应"""
    model: str
    provider: str
    data: list[EmbeddingData]
    usage: Usage
