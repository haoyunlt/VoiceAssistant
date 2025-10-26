"""Token计数与成本计算器."""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# 模型定价表 (USD per 1K tokens)
MODEL_PRICING = {
    # OpenAI
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-32k": {"input": 0.06, "output": 0.12},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4-vision-preview": {"input": 0.01, "output": 0.03},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0},

    # Claude
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},

    # 智谱AI
    "glm-4": {"input": 0.001, "output": 0.001},
    "glm-3-turbo": {"input": 0.0005, "output": 0.0005},
    "embedding-2": {"input": 0.0001, "output": 0},
}


class TokenCounter:
    """Token计数器."""

    @staticmethod
    def count_message_tokens(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo") -> int:
        """
        计算消息列表的token数.

        这是一个粗略估算。
        更准确的方法需要使用对应模型的tokenizer (如tiktoken)。

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
                # 多模态内容 (文本 + 图片)
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            total_tokens += TokenCounter._estimate_tokens(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            # 图片token估算 (根据size)
                            total_tokens += 85  # Claude默认

        # 回复的固定开销
        total_tokens += 3

        return total_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        估算文本token数.

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


class CostCalculator:
    """成本计算器."""

    @staticmethod
    def calculate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, float]:
        """
        计算成本.

        Args:
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            成本详情字典:
            - input_cost: 输入成本
            - output_cost: 输出成本
            - total_cost: 总成本
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
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
    ) -> Dict[str, float]:
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

        return cost

    @staticmethod
    def compare_model_costs(
        models: List[str],
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, Dict[str, float]]:
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
        models: List[str],
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[str, Dict[str, float]]:
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
    def calculate_savings(
        current_model: str,
        alternative_model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Dict[str, float]:
        """
        计算切换模型可节省的成本.

        Args:
            current_model: 当前模型
            alternative_model: 替代模型
            input_tokens: 输入token数
            output_tokens: 输出token数

        Returns:
            节省详情
        """
        current_cost = CostCalculator.calculate_cost(
            current_model, input_tokens, output_tokens
        )

        alternative_cost = CostCalculator.calculate_cost(
            alternative_model, input_tokens, output_tokens
        )

        savings = current_cost["total_cost"] - alternative_cost["total_cost"]
        savings_percent = (savings / current_cost["total_cost"]) * 100 if current_cost["total_cost"] > 0 else 0

        return {
            "current_cost": current_cost["total_cost"],
            "alternative_cost": alternative_cost["total_cost"],
            "savings": round(savings, 6),
            "savings_percent": round(savings_percent, 2),
            "currency": "USD",
        }


class UsageTracker:
    """使用量追踪器."""

    def __init__(self):
        """初始化追踪器."""
        self.usage_history: List[Dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        timestamp: Optional[str] = None,
    ):
        """
        记录使用量.

        Args:
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
            timestamp: 时间戳
        """
        from datetime import datetime

        cost = CostCalculator.calculate_cost(model, input_tokens, output_tokens)

        usage_record = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost["total_cost"],
            "timestamp": timestamp or datetime.utcnow().isoformat(),
        }

        self.usage_history.append(usage_record)

        # 更新总计
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost["total_cost"]

    def get_summary(self) -> Dict[str, any]:
        """
        获取使用摘要.

        Returns:
            使用摘要
        """
        return {
            "total_requests": len(self.usage_history),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": round(self.total_cost, 6),
            "currency": "USD",
            "average_cost_per_request": round(
                self.total_cost / len(self.usage_history), 6
            ) if self.usage_history else 0,
        }

    def get_cost_by_model(self) -> Dict[str, float]:
        """
        按模型获取成本.

        Returns:
            每个模型的总成本
        """
        cost_by_model = {}

        for record in self.usage_history:
            model = record["model"]
            cost = record["cost"]

            if model not in cost_by_model:
                cost_by_model[model] = 0.0

            cost_by_model[model] += cost

        # 四舍五入
        for model in cost_by_model:
            cost_by_model[model] = round(cost_by_model[model], 6)

        return cost_by_model

    def reset(self):
        """重置追踪器."""
        self.usage_history.clear()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
