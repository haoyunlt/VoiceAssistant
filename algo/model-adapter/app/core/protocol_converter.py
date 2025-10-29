"""协议转换器 - 统一不同Provider的API格式."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolConverter:
    """
    协议转换器.

    负责将统一格式转换为各Provider的特定格式，
    以及将Provider的响应转换为统一格式。
    """

    @staticmethod
    def to_openai_format(
        messages: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        转换为OpenAI格式.

        Args:
            messages: 统一格式的消息列表
            parameters: 参数

        Returns:
            OpenAI API格式的请求
        """
        request = {
            "messages": messages,
        }

        if parameters:
            # 映射参数
            param_mapping = {
                "temperature": "temperature",
                "max_tokens": "max_tokens",
                "top_p": "top_p",
                "frequency_penalty": "frequency_penalty",
                "presence_penalty": "presence_penalty",
                "stop": "stop",
            }

            for unified_key, openai_key in param_mapping.items():
                if unified_key in parameters:
                    request[openai_key] = parameters[unified_key]

        return request

    @staticmethod
    def to_claude_format(
        messages: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        转换为Claude格式.

        Claude需要将system消息分离。

        Args:
            messages: 统一格式的消息列表
            parameters: 参数

        Returns:
            Claude API格式的请求
        """
        system_prompt = None
        formatted_messages = []

        # 分离system消息
        for msg in messages:
            if msg.get("role") == "system":
                if system_prompt is None:
                    system_prompt = msg.get("content", "")
                else:
                    system_prompt += "\n\n" + msg.get("content", "")
            else:
                formatted_messages.append(msg)

        request = {
            "messages": formatted_messages,
        }

        if system_prompt:
            request["system"] = system_prompt

        if parameters:
            # 映射参数
            param_mapping = {
                "temperature": "temperature",
                "max_tokens": "max_tokens",
                "top_p": "top_p",
                "top_k": "top_k",
                "stop": "stop_sequences",
            }

            for unified_key, claude_key in param_mapping.items():
                if unified_key in parameters:
                    request[claude_key] = parameters[unified_key]

        return request

    @staticmethod
    def to_zhipu_format(
        messages: list[dict[str, Any]],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        转换为智谱AI格式.

        Args:
            messages: 统一格式的消息列表
            parameters: 参数

        Returns:
            智谱AI API格式的请求
        """
        request = {
            "messages": messages,
        }

        if parameters:
            # 映射参数
            param_mapping = {
                "temperature": "temperature",
                "max_tokens": "max_tokens",
                "top_p": "top_p",
            }

            for unified_key, zhipu_key in param_mapping.items():
                if unified_key in parameters:
                    request[zhipu_key] = parameters[unified_key]

        return request

    @staticmethod
    def from_openai_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        从OpenAI响应转换为统一格式.

        Args:
            response: OpenAI API响应

        Returns:
            统一格式响应
        """
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = response.get("usage", {})

        unified_response = {
            "provider": "openai",
            "model": response.get("model"),
            "content": message.get("content"),
            "finish_reason": choice.get("finish_reason"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "metadata": {
                "id": response.get("id"),
                "created": response.get("created"),
            },
        }

        # 处理函数调用
        if "function_call" in message:
            unified_response["function_call"] = {
                "name": message["function_call"]["name"],
                "arguments": message["function_call"]["arguments"],
            }

        return unified_response

    @staticmethod
    def from_claude_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        从Claude响应转换为统一格式.

        Args:
            response: Claude API响应

        Returns:
            统一格式响应
        """
        # 提取文本内容
        content = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = response.get("usage", {})

        return {
            "provider": "claude",
            "model": response.get("model"),
            "content": content,
            "finish_reason": response.get("stop_reason"),
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            "metadata": {
                "id": response.get("id"),
                "type": response.get("type"),
                "role": response.get("role"),
            },
        }

    @staticmethod
    def from_zhipu_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        从智谱AI响应转换为统一格式.

        Args:
            response: 智谱AI API响应

        Returns:
            统一格式响应
        """
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = response.get("usage", {})

        unified_response = {
            "provider": "zhipu",
            "model": response.get("model"),
            "content": message.get("content"),
            "finish_reason": choice.get("finish_reason"),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "metadata": {
                "id": response.get("id"),
                "created": response.get("created"),
            },
        }

        # 处理工具调用
        if "tool_calls" in message and message["tool_calls"]:
            tool_call = message["tool_calls"][0]
            unified_response["function_call"] = {
                "name": tool_call["function"]["name"],
                "arguments": tool_call["function"]["arguments"],
            }

        return unified_response

    @staticmethod
    def convert_functions_to_tools(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        将OpenAI functions格式转换为tools格式 (用于Claude/智谱).

        Args:
            functions: OpenAI functions定义

        Returns:
            tools定义
        """
        tools = []

        for func in functions:
            tool = {
                "type": "function",
                "function": {
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "parameters": func.get("parameters", {}),
                },
            }
            tools.append(tool)

        return tools

    @staticmethod
    def normalize_messages(
        messages: list[dict[str, Any]],
        provider: str,
    ) -> list[dict[str, Any]]:
        """
        规范化消息格式.

        不同Provider对消息格式有不同要求，
        此方法确保消息符合特定Provider的规范。

        Args:
            messages: 消息列表
            provider: 目标Provider

        Returns:
            规范化后的消息列表
        """
        if provider == "claude":
            # Claude不允许连续的相同role消息
            normalized = []
            last_role = None

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")

                if role == "system":
                    # system消息会被单独处理
                    normalized.append(msg)
                elif role == last_role:
                    # 合并连续的相同role消息
                    if normalized:
                        normalized[-1]["content"] += "\n\n" + content
                else:
                    normalized.append(msg)
                    last_role = role

            return normalized

        elif provider == "zhipu":
            # 智谱AI要求必须有user消息
            if not any(msg.get("role") == "user" for msg in messages):
                # 添加一个默认user消息
                messages.append({"role": "user", "content": "请继续"})

            return messages

        else:
            # OpenAI等：不需要特殊处理
            return messages

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算文本的token数量.

        这是一个粗略估算，实际token数可能不同。
        更准确的计算需要使用对应模型的tokenizer。

        Args:
            text: 文本

        Returns:
            预估token数
        """
        # 粗略估算: 1 token ≈ 4 characters (英文)
        # 中文: 1 token ≈ 1.5 characters

        # 简单判断是否包含中文
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars

        estimated_tokens = int(chinese_chars / 1.5 + english_chars / 4)

        return max(1, estimated_tokens)
