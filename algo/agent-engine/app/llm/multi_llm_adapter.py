"""
Multi-LLM Adapter

多厂商 LLM 适配器，支持：
- OpenAI (GPT-4, GPT-3.5)
- Claude (Claude-3)
- Ollama (本地 LLM)

自动降级策略：
OpenAI -> Claude -> Ollama
"""

import os
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import logging
from app.llm.base import CompletionResponse, LLMClient, Message

logger = logging.getLogger(__name__)


class MultiLLMAdapter:
    """多厂商 LLM 适配器"""

    def __init__(
        self,
        preferred_provider: Literal["openai", "claude", "ollama"] = "openai",
        openai_model: str = "gpt-4-turbo-preview",
        claude_model: str = "claude-3-sonnet-20240229",
        ollama_model: str = "llama2",
        openai_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
    ):
        """
        初始化多厂商 LLM 适配器

        Args:
            preferred_provider: 首选提供商（openai | claude | ollama）
            openai_model: OpenAI 模型名称
            claude_model: Claude 模型名称
            ollama_model: Ollama 模型名称
            openai_api_key: OpenAI API 密钥
            claude_api_key: Claude API 密钥
            ollama_base_url: Ollama 服务地址
        """
        self.preferred_provider = preferred_provider

        # 初始化各个客户端
        self.openai_client = None
        self.claude_client = None
        self.ollama_client = None

        # 尝试初始化 OpenAI
        if openai_api_key or os.getenv("OPENAI_API_KEY"):
            try:
                from app.llm.openai_client import OpenAIClient

                self.openai_client = OpenAIClient(
                    model=openai_model, api_key=openai_api_key
                )
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # 尝试初始化 Claude
        if claude_api_key or os.getenv("ANTHROPIC_API_KEY"):
            try:
                from app.llm.claude_client import ClaudeClient

                self.claude_client = ClaudeClient(
                    model=claude_model, api_key=claude_api_key
                )
                logger.info("Claude client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude: {e}")

        # 尝试初始化 Ollama
        try:
            from app.llm.ollama_client import OllamaClient

            self.ollama_client = OllamaClient(
                model=ollama_model, base_url=ollama_base_url
            )
            logger.info("Ollama client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama: {e}")

        logger.info(f"Multi-LLM adapter initialized (preferred: {preferred_provider})")

    async def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        provider_override: Optional[Literal["openai", "claude", "ollama"]] = None,
        **kwargs,
    ) -> tuple[CompletionResponse, str]:
        """
        生成完成响应（带自动降级）

        降级策略：
        1. 尝试首选提供商
        2. 如果失败，尝试其他提供商
        3. 如果都失败，抛出异常

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            tools: 可用工具列表
            provider_override: 提供商覆盖（临时使用）
            **kwargs: 其他参数

        Returns:
            (CompletionResponse, provider_name)
        """
        # 确定提供商顺序
        provider = provider_override or self.preferred_provider

        if provider == "openai":
            providers_to_try = ["openai", "claude", "ollama"]
        elif provider == "claude":
            providers_to_try = ["claude", "openai", "ollama"]
        else:  # ollama
            providers_to_try = ["ollama", "openai", "claude"]

        last_error = None

        for prov in providers_to_try:
            client = self._get_client(prov)
            if not client:
                continue

            try:
                logger.info(f"Trying {prov} for completion...")
                response = await client.complete(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    **kwargs,
                )
                logger.info(f"Completion succeeded with {prov}")
                return response, prov

            except Exception as e:
                logger.warning(f"{prov} completion failed: {e}")
                last_error = e
                continue

        # 所有提供商都失败
        raise Exception(
            f"All LLM providers failed. Last error: {last_error}"
        )

    async def complete_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        provider_override: Optional[Literal["openai", "claude", "ollama"]] = None,
        **kwargs,
    ) -> tuple[AsyncIterator[str], str]:
        """
        生成完成响应（流式，带自动降级）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            tools: 可用工具列表
            provider_override: 提供商覆盖
            **kwargs: 其他参数

        Returns:
            (AsyncIterator[str], provider_name)
        """
        # 确定提供商顺序
        provider = provider_override or self.preferred_provider

        if provider == "openai":
            providers_to_try = ["openai", "claude", "ollama"]
        elif provider == "claude":
            providers_to_try = ["claude", "openai", "ollama"]
        else:
            providers_to_try = ["ollama", "openai", "claude"]

        last_error = None

        for prov in providers_to_try:
            client = self._get_client(prov)
            if not client:
                continue

            try:
                logger.info(f"Trying {prov} for streaming completion...")
                stream = client.complete_stream(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    **kwargs,
                )
                logger.info(f"Streaming started with {prov}")
                return stream, prov

            except Exception as e:
                logger.warning(f"{prov} streaming failed: {e}")
                last_error = e
                continue

        # 所有提供商都失败
        raise Exception(
            f"All LLM providers failed for streaming. Last error: {last_error}"
        )

    def _get_client(self, provider: str) -> Optional[LLMClient]:
        """
        获取指定提供商的客户端

        Args:
            provider: 提供商名称

        Returns:
            LLM 客户端或 None
        """
        if provider == "openai":
            return self.openai_client
        elif provider == "claude":
            return self.claude_client
        elif provider == "ollama":
            return self.ollama_client
        else:
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        获取所有 LLM 提供商的状态

        Returns:
            状态字典
        """
        status = {
            "preferred_provider": self.preferred_provider,
            "providers": {},
        }

        # OpenAI 状态
        if self.openai_client:
            status["providers"]["openai"] = self.openai_client.health_check()
        else:
            status["providers"]["openai"] = {
                "healthy": False,
                "error": "OpenAI not configured or failed to initialize",
            }

        # Claude 状态
        if self.claude_client:
            status["providers"]["claude"] = self.claude_client.health_check()
        else:
            status["providers"]["claude"] = {
                "healthy": False,
                "error": "Claude not configured or failed to initialize",
            }

        # Ollama 状态
        if self.ollama_client:
            status["providers"]["ollama"] = self.ollama_client.health_check()
        else:
            status["providers"]["ollama"] = {
                "healthy": False,
                "error": "Ollama not configured or failed to initialize",
            }

        return status


# 全局实例
_multi_llm_adapter: Optional[MultiLLMAdapter] = None


def get_multi_llm_adapter() -> MultiLLMAdapter:
    """
    获取多厂商 LLM 适配器实例（单例）

    Returns:
        MultiLLMAdapter 实例
    """
    global _multi_llm_adapter

    if _multi_llm_adapter is None:
        # 从环境变量读取配置
        preferred_provider = os.getenv("PREFERRED_LLM_PROVIDER", "openai")

        _multi_llm_adapter = MultiLLMAdapter(
            preferred_provider=preferred_provider,  # type: ignore
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama2"),
        )

    return _multi_llm_adapter
