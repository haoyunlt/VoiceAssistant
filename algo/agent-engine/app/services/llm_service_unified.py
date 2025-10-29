"""LLM服务 - 使用统一LLM客户端（重构版）"""
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

from llm_client import UnifiedLLMClient

logger = logging.getLogger(__name__)


class LLMService:
    """
    大语言模型服务 - 通过model-adapter统一调用

    替代原有的直连OpenAI方式
    """

    def __init__(self):
        """初始化LLM服务"""
        # 使用统一LLM客户端
        self.client = UnifiedLLMClient(
            model_adapter_url=os.getenv("MODEL_ADAPTER_URL", "http://model-adapter:8005"),
            default_model=os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo"),
            timeout=int(os.getenv("TIMEOUT_SECONDS", "60")),
        )
        logger.info("LLMService initialized with UnifiedLLMClient (via model-adapter)")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        调用LLM Chat接口

        Args:
            messages: 对话历史 [{"role": "user", "content": "..."}]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLM响应字典 {"content": "...", "usage": {...}, ...}
        """
        try:
            result = await self.client.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 返回完整响应（包含usage等信息）
            return result

        except Exception as e:
            logger.error(f"LLM chat request failed: {e}", exc_info=True)
            raise

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        简单生成接口

        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            生成的文本
        """
        try:
            text = await self.client.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return text

        except Exception as e:
            logger.error(f"LLM generate request failed: {e}", exc_info=True)
            raise
