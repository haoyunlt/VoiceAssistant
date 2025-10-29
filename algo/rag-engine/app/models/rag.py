"""RAG相关数据模型"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrievedDocument(BaseModel):
    """检索到的文档"""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGRequest(BaseModel):
    """RAG请求"""
    query: str = Field(..., description="用户查询")
    knowledge_base_id: str = Field(..., description="知识库ID")
    tenant_id: str = Field(..., description="租户ID")
    conversation_id: str | None = Field(default=None, description="对话ID")
    history: list[dict[str, str]] = Field(default_factory=list, description="对话历史")
    top_k: int = Field(default=5, description="返回top-k结果")
    enable_rerank: bool = Field(default=True, description="是否启用重排序")
    model: str | None = Field(default=None, description="LLM模型")
    temperature: float = Field(default=0.7, description="温度参数")
    stream: bool = Field(default=False, description="是否流式响应")


class RAGResponse(BaseModel):
    """RAG响应"""
    query: str
    answer: str
    sources: list[RetrievedDocument]
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_time: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QueryExpansionResult(BaseModel):
    """查询扩展结果"""
    original_query: str
    expanded_queries: list[str]
    keywords: list[str] = Field(default_factory=list)


class RerankResult(BaseModel):
    """重排序结果"""
    documents: list[RetrievedDocument]
    scores: list[float]
