"""
Claude (Anthropic) LLM Client

Claude API 客户端实现
"""

import os
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    AsyncAnthropic = None

import logging
from app.llm.base import CompletionResponse, LLMClient, Message

logger = logging.getLogger(__name__)


class ClaudeClient(LLMClient):
    """Claude (Anthropic) LLM 客户端"""

    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化 Claude 客户端

        Args:
            model: 模型名称（claude-3-opus, claude-3-sonnet, claude-3-haiku）
            api_key: Anthropic API 密钥
            base_url: API 基础 URL（可选）
            **kwargs: 其他参数
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "Anthropic SDK not installed. "
                "Install it with: pip install anthropic"
            )

        super().__init__(model, api_key, base_url, **kwargs)

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            logger.warning(
                "Anthropic API key not provided. "
                "Set ANTHROPIC_API_KEY environment variable or pass it to constructor."
            )

        # 初始化客户端
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = AsyncAnthropic(**client_kwargs) if self.api_key else None

        logger.info(f"Claude client initialized (model: {self.model})")

    def _convert_messages_to_claude_format(
        self, messages: List[Message]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        转换消息为 Claude 格式

        Claude 需要将 system 消息单独提取

        Args:
            messages: Message 对象列表

        Returns:
            (system_prompt, claude_messages)
        """
        system_prompt = None
        claude_messages = []

        for msg in messages:
            if msg.role == "system":
                # Claude 使用独立的 system 参数
                if system_prompt is None:
                    system_prompt = msg.content
                else:
                    system_prompt += "\n\n" + msg.content
            else:
                # 其他消息保持原样
                claude_messages.append(
                    {"role": msg.role, "content": msg.content}
                )

        return system_prompt, claude_messages

    async def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        生成完成响应（非流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-1, Claude 范围较窄)
            max_tokens: 最大 token 数
            tools: 可用工具列表（Claude Tool Use 格式）
            **kwargs: 其他参数

        Returns:
            CompletionResponse 对象
        """
        if not self.client:
            raise ValueError("Claude client not initialized (missing API key)")

        try:
            # 转换消息格式
            system_prompt, claude_messages = self._convert_messages_to_claude_format(
                messages
            )

            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": claude_messages,
                "temperature": min(temperature, 1.0),  # Claude 最大为 1.0
                "max_tokens": max_tokens,
                **kwargs,
            }

            # 添加 system prompt
            if system_prompt:
                request_params["system"] = system_prompt

            # 添加工具（如果提供）
            if tools:
                # 转换为 Claude Tool Use 格式
                claude_tools = self._convert_tools_to_claude_format(tools)
                request_params["tools"] = claude_tools

            # 调用 Claude API
            response = await self.client.messages.create(**request_params)

            # 解析响应
            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": str(block.input),
                            },
                        }
                    )

            # 构建响应
            return CompletionResponse(
                content=content,
                model=response.model,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                }
                if response.usage
                else None,
                tool_calls=tool_calls if tool_calls else None,
            )

        except Exception as e:
            logger.error(f"Claude completion failed: {e}", exc_info=True)
            raise

    async def complete_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        生成完成响应（流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-1)
            max_tokens: 最大 token 数
            tools: 可用工具列表
            **kwargs: 其他参数

        Yields:
            生成的文本块
        """
        if not self.client:
            raise ValueError("Claude client not initialized (missing API key)")

        try:
            # 转换消息格式
            system_prompt, claude_messages = self._convert_messages_to_claude_format(
                messages
            )

            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": claude_messages,
                "temperature": min(temperature, 1.0),
                "max_tokens": max_tokens,
                **kwargs,
            }

            # 添加 system prompt
            if system_prompt:
                request_params["system"] = system_prompt

            # 添加工具（如果提供）
            if tools:
                claude_tools = self._convert_tools_to_claude_format(tools)
                request_params["tools"] = claude_tools

            # 调用 Claude API（流式）
            async with self.client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Claude streaming completion failed: {e}", exc_info=True)
            raise

    def _convert_tools_to_claude_format(
        self, openai_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        转换 OpenAI 工具格式到 Claude 格式

        Args:
            openai_tools: OpenAI Function Calling 格式的工具

        Returns:
            Claude Tool Use 格式的工具
        """
        claude_tools = []

        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                claude_tool = {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
                claude_tools.append(claude_tool)

        return claude_tools

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not ANTHROPIC_AVAILABLE:
            return {
                "healthy": False,
                "error": "Anthropic SDK not installed",
            }

        if not self.api_key:
            return {
                "healthy": False,
                "error": "Anthropic API key not configured",
            }

        return {
            "healthy": True,
            "model": self.model,
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
        }
