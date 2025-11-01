"""请求模型"""

from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息模型"""

    role: str = Field(..., description="角色：system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""

    model: str = Field(..., description="模型名称")
    messages: list[Message] = Field(..., description="对话历史")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int | None = Field(default=None, description="最大Token数")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p采样")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="存在惩罚")
    stream: bool = Field(default=False, description="是否流式响应")
    provider: str | None = Field(default=None, description="指定提供商")


class CompletionRequest(BaseModel):
    """补全请求"""

    model: str = Field(..., description="模型名称")
    prompt: str = Field(..., description="提示词")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int | None = Field(default=None, description="最大Token数")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p采样")
    stream: bool = Field(default=False, description="是否流式响应")
    provider: str | None = Field(default=None, description="指定提供商")


class EmbeddingRequest(BaseModel):
    """向量化请求"""

    model: str = Field(..., description="模型名称")
    input: list[str] = Field(..., description="输入文本列表")
    provider: str | None = Field(default=None, description="指定提供商")
