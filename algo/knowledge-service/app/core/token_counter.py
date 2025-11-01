"""
Token Counter - LLM Token计量与成本估算

用于追踪LLM调用的Token消耗和成本
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token计数器"""

    # 模型定价（美元/1K tokens）
    PRICING = {
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4-turbo": {"prompt": 0.001, "completion": 0.003},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        # Claude models
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        # Qwen models (approximate)
        "qwen-max": {"prompt": 0.0002, "completion": 0.0006},
        "qwen-plus": {"prompt": 0.0001, "completion": 0.0003},
    }

    def __init__(self):
        """初始化Token计数器"""
        self.encodings = {}
        self._init_tiktoken()

    def _init_tiktoken(self):
        """初始化tiktoken编码器"""
        try:
            import tiktoken

            self.tiktoken = tiktoken
            self.tiktoken_available = True
            logger.info("tiktoken initialized successfully")
        except ImportError:
            logger.warning("tiktoken not available, using approximate token counting")
            self.tiktoken = None
            self.tiktoken_available = False

    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """
        计算Token数量

        Args:
            text: 文本内容
            model: 模型名称

        Returns:
            Token数量
        """
        if not text:
            return 0

        if self.tiktoken_available:
            return self._count_tokens_tiktoken(text, model)
        else:
            return self._count_tokens_approximate(text)

    def _count_tokens_tiktoken(self, text: str, model: str) -> int:
        """使用tiktoken精确计数"""
        try:
            # 获取或创建编码器
            if model not in self.encodings:
                try:
                    self.encodings[model] = self.tiktoken.encoding_for_model(model)
                except KeyError:
                    # 模型不存在，使用cl100k_base（GPT-4默认）
                    logger.warning(f"Model {model} not found, using cl100k_base encoding")
                    self.encodings[model] = self.tiktoken.get_encoding("cl100k_base")

            return len(self.encodings[model].encode(text))

        except Exception as e:
            logger.warning(f"tiktoken counting failed: {e}, using approximate")
            return self._count_tokens_approximate(text)

    def _count_tokens_approximate(self, text: str) -> int:
        """近似计数（英文约4字符=1token，中文约1.5字符=1token）"""
        # 简单启发式：检测中文字符
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        english_chars = len(text) - chinese_chars

        # 中文: 1.5字符/token, 英文: 4字符/token
        return int(chinese_chars / 1.5 + english_chars / 4)

    def estimate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o-mini"
    ) -> float:
        """
        估算成本

        Args:
            prompt_tokens: Prompt Token数量
            completion_tokens: Completion Token数量
            model: 模型名称

        Returns:
            成本（美元）
        """
        pricing = self.PRICING.get(
            model,
            {"prompt": 0.00015, "completion": 0.0006},  # 默认使用gpt-4o-mini
        )

        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]

        return prompt_cost + completion_cost

    def get_model_info(self, model: str) -> dict[str, Any]:
        """
        获取模型信息

        Args:
            model: 模型名称

        Returns:
            模型信息
        """
        pricing = self.PRICING.get(model)

        if pricing:
            return {
                "model": model,
                "prompt_price_per_1k": pricing["prompt"],
                "completion_price_per_1k": pricing["completion"],
                "available": True,
            }
        else:
            return {
                "model": model,
                "available": False,
                "message": "Model pricing not configured",
            }

    def compare_costs(
        self, prompt_tokens: int, completion_tokens: int, models: list[str]
    ) -> list[dict[str, Any]]:
        """
        比较多个模型的成本

        Args:
            prompt_tokens: Prompt Token数量
            completion_tokens: Completion Token数量
            models: 模型列表

        Returns:
            成本比较结果
        """
        results = []

        for model in models:
            cost = self.estimate_cost(prompt_tokens, completion_tokens, model)
            results.append(
                {
                    "model": model,
                    "cost_usd": cost,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            )

        # 按成本排序
        results.sort(key=lambda x: x["cost_usd"])
        return results


# 全局实例
_token_counter: TokenCounter | None = None


def get_token_counter() -> TokenCounter:
    """
    获取Token计数器实例（单例）

    Returns:
        TokenCounter实例
    """
    global _token_counter

    if _token_counter is None:
        _token_counter = TokenCounter()

    return _token_counter
