from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAdapter(ABC):
    """
    模型适配器基类，所有具体的适配器必须继承此类。
    """

    def __init__(self):
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens_used": 0,
            "total_cost_usd": 0.0,
        }

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        聊天补全接口。

        Args:
            model: 模型名称
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数 (0.0 - 2.0)
            max_tokens: 最大 token 数
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "text": "生成的文本",
                "input_tokens": 123,
                "output_tokens": 456,
                "tokens_used": 579,
                "cost_usd": 0.01,
                "model": "gpt-4",
                "finish_reason": "stop"
            }
        """
        pass

    @abstractmethod
    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        嵌入向量生成接口。

        Args:
            model: 模型名称
            input: 输入文本或文本列表
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {
                "embeddings": [[0.1, 0.2, ...], ...],
                "model": "text-embedding-ada-002",
                "tokens_used": 10,
                "cost_usd": 0.0001
            }
        """
        pass

    async def get_stats(self) -> Dict[str, Any]:
        """获取适配器的统计信息"""
        return self.stats

    async def close(self):
        """关闭适配器，清理资源"""
        pass
