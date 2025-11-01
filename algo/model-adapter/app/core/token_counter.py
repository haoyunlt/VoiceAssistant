"""改进的Token计数与成本计算 - 使用tiktoken提升精度."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入tiktoken
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    logger.warning("tiktoken not installed, using fallback estimation")
    TIKTOKEN_AVAILABLE = False


# 模型定价表 (USD per 1K tokens) - 2024最新价格
MODEL_PRICING = {
    # OpenAI GPT-4 Series
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-32k": {"input": 0.06, "output": 0.12},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4-1106-preview": {"input": 0.01, "output": 0.03},
    "gpt-4-vision-preview": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},  # GPT-4o (2024)
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},  # GPT-4o-mini (2024)

    # OpenAI GPT-3.5 Series
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    "gpt-3.5-turbo-1106": {"input": 0.001, "output": 0.002},

    # OpenAI Embedding
    "text-embedding-ada-002": {"input": 0.0001, "output": 0},
    "text-embedding-3-small": {"input": 0.00002, "output": 0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0},

    # Claude 3 Series
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-5-sonnet-20240620": {"input": 0.003, "output": 0.015},  # Claude 3.5

    # 智谱AI
    "glm-4": {"input": 0.001, "output": 0.001},
    "glm-4-plus": {"input": 0.0015, "output": 0.0015},
    "glm-3-turbo": {"input": 0.0005, "output": 0.0005},
    "embedding-2": {"input": 0.0001, "output": 0},

    # 通义千问
    "qwen-max": {"input": 0.002, "output": 0.002},
    "qwen-plus": {"input": 0.001, "output": 0.001},
    "qwen-turbo": {"input": 0.0003, "output": 0.0003},

    # 百度文心
    "ERNIE-Bot-4": {"input": 0.0012, "output": 0.0012},
    "ERNIE-Bot-turbo": {"input": 0.0008, "output": 0.0008},
}


class TokenCounter:
    """Token计数器 (tiktoken优先，fallback到估算)."""

    @staticmethod
    def count_tokens(
        text: str,
        model: str = "gpt-3.5-turbo",
    ) -> int:
        """
        计算文本token数.

        Args:
            text: 文本
            model: 模型名称

        Returns:
            Token数
        """
        if TIKTOKEN_AVAILABLE:
            try:
                encoding = tiktoken.encoding_for_model(model)
                return len(encoding.encode(text))
            except Exception as e:
                logger.debug(f"tiktoken failed for {model}: {e}, using fallback")
                # Fall through to estimation

        # Fallback: 估算
        return TokenCounter._estimate_tokens(text)

    @staticmethod
    def count_message_tokens(
        messages: list[dict[str, str]],
        model: str = "gpt-3.5-turbo",
    ) -> int:
        """
        计算消息列表token数.

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            预估token数
        """
        if TIKTOKEN_AVAILABLE:
            try:
                encoding = tiktoken.encoding_for_model(model)

                # 每条消息的固定开销
                tokens_per_message = 4 if "gpt-3.5" in model else 3
                total_tokens = 0

                for message in messages:
                    total_tokens += tokens_per_message
                    # role token
                    total_tokens += len(encoding.encode(message.get("role", "")))
                    # content token
                    content = message.get("content", "")
                    if isinstance(content, str):
                        total_tokens += len(encoding.encode(content))
                    elif isinstance(content, list):
                        # 多模态内容
                        for item in content:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    text = item.get("text", "")
                                    total_tokens += len(encoding.encode(text))
                                elif item.get("type") == "image_url":
                                    # 图片token估算 (Claude/GPT-4V)
                                    total_tokens += 85

                # 回复的固定开销
                total_tokens += 3

                return total_tokens

            except Exception as e:
                logger.debug(f"tiktoken failed for {model}: {e}, using fallback")
                # Fall through to estimation

        # Fallback: 估算
        return TokenCounter._estimate_message_tokens_fallback(messages, model)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        估算文本token数 (fallback方法).

        Args:
            text: 文本

        Returns:
            预估token数
        """
        # 统计中文和英文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars

        # 中文: ~1.5 chars per token
        # 英文: ~4 chars per token
        estimated = int(chinese_chars / 1.5 + other_chars / 4)

        return max(1, estimated)

    @staticmethod
    def _estimate_message_tokens_fallback(
        messages: list[dict[str, str]],
        model: str,
    ) -> int:
        """
        估算消息列表token数 (fallback方法).

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            预估token数
        """
        total_tokens = 0

        # 每条消息的固定开销
        tokens_per_message = 4 if "gpt-3.5" in model else 3

        for message in messages:
            # 消息固定开销
            total_tokens += tokens_per_message

            # role token
            total_tokens += TokenCounter._estimate_tokens(message.get("role", ""))

            # content token
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += TokenCounter._estimate_tokens(content)
            elif isinstance(content, list):
                # 多模态内容
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            total_tokens += TokenCounter._estimate_tokens(
                                item.get("text", "")
                            )
                        elif item.get("type") == "image_url":
                            # 图片token估算
                            total_tokens += 85

        # 回复的固定开销
        total_tokens += 3

        return total_tokens


class CostCalculator:
    """成本计算器."""

    @staticmethod
    def calculate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, float]:
        """
        计算成本.

        Args:
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            成本详情字典
        """
        # 获取定价
        pricing = MODEL_PRICING.get(model)

        if not pricing:
            logger.warning(f"No pricing found for model: {model}, using default")
            pricing = {"input": 0.001, "output": 0.002}

        # 计算成本 (per 1K tokens)
        input_cost = (input_tokens / 1000.0) * pricing["input"]
        output_cost = (output_tokens / 1000.0) * pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "currency": "USD",
        }

    @staticmethod
    def estimate_request_cost(
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
    ) -> dict[str, float]:
        """
        估算请求成本.

        Args:
            model: 模型名称
            messages: 消息列表
            max_tokens: 最大输出token数

        Returns:
            成本估算
        """
        # 估算输入token
        input_tokens = TokenCounter.count_message_tokens(messages, model)

        # 使用max_tokens作为输出token估算
        output_tokens = max_tokens

        # 计算成本
        cost = CostCalculator.calculate_cost(model, input_tokens, output_tokens)
        cost["estimated"] = True
        cost["input_tokens"] = input_tokens
        cost["output_tokens_estimated"] = output_tokens

        return cost

    @staticmethod
    def compare_model_costs(
        models: list[str],
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, dict[str, float]]:
        """
        比较多个模型的成本.

        Args:
            models: 模型列表
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            每个模型的成本
        """
        comparison = {}

        for model in models:
            comparison[model] = CostCalculator.calculate_cost(
                model, input_tokens, output_tokens
            )

        return comparison

    @staticmethod
    def get_cheapest_model(
        models: list[str],
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[str, dict[str, float]]:
        """
        获取成本最低的模型.

        Args:
            models: 模型列表
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            (模型名称, 成本详情)
        """
        comparison = CostCalculator.compare_model_costs(
            models, input_tokens, output_tokens
        )

        if not comparison:
            return "", {}

        # 找出总成本最低的
        cheapest = min(comparison.items(), key=lambda x: x[1]["total_cost"])

        return cheapest[0], cheapest[1]

    @staticmethod
    def get_model_pricing() -> dict[str, dict[str, float]]:
        """
        获取所有模型定价.

        Returns:
            定价表
        """
        return MODEL_PRICING.copy()


# Prometheus指标
from prometheus_client import Counter, Histogram

# Token使用量
tokens_used_total = Counter(
    "model_adapter_tokens_used_total",
    "Total tokens used",
    ["provider", "model", "type"],  # type: input/output
)

# 成本
cost_usd_total = Counter(
    "model_adapter_cost_usd_total",
    "Total cost in USD",
    ["provider", "model"],
)

# Token计数延迟
token_counting_duration_seconds = Histogram(
    "model_adapter_token_counting_duration_seconds",
    "Token counting duration",
    ["method"],  # tiktoken/fallback
)


def record_token_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
):
    """
    记录token使用量和成本.

    Args:
        provider: 提供商
        model: 模型名称
        input_tokens: 输入token数
        output_tokens: 输出token数
    """
    # 记录token使用
    tokens_used_total.labels(
        provider=provider,
        model=model,
        type="input",
    ).inc(input_tokens)

    tokens_used_total.labels(
        provider=provider,
        model=model,
        type="output",
    ).inc(output_tokens)

    # 计算并记录成本
    cost_data = CostCalculator.calculate_cost(model, input_tokens, output_tokens)
    cost_usd_total.labels(
        provider=provider,
        model=model,
    ).inc(cost_data["total_cost"])
