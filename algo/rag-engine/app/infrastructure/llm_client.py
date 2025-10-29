"""
LLM Client - 大模型客户端

支持多种 LLM 提供商：
- OpenAI
- Anthropic
- Azure OpenAI
- 本地模型
"""

import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端"""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4-turbo-preview",
        api_key: str = None,
        base_url: str = None,
    ):
        """
        初始化 LLM 客户端

        Args:
            provider: 提供商 (openai/anthropic/azure)
            model: 模型名称
            api_key: API 密钥
            base_url: API 基础 URL
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key or self._get_api_key_from_env()
        self.base_url = base_url
        self.client = None

        logger.info(f"LLM client created: provider={provider}, model={model}")

    async def initialize(self):
        """初始化 LLM 客户端"""
        if self.provider == "openai":
            await self._initialize_openai()
        elif self.provider == "anthropic":
            await self._initialize_anthropic()
        elif self.provider == "azure":
            await self._initialize_azure()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        logger.info("LLM client initialized")

    async def _initialize_openai(self):
        """初始化 OpenAI 客户端（通过model-adapter统一路由）"""
        try:
            import os

            from openai import AsyncOpenAI

            # 优先使用model-adapter进行统一LLM调用
            model_adapter_url = os.getenv("MODEL_ADAPTER_URL", "http://model-adapter:8005")
            effective_base_url = self.base_url or f"{model_adapter_url}/api/v1"

            self.client = AsyncOpenAI(
                api_key=self.api_key or "dummy-key",
                base_url=effective_base_url,
            )
            logger.info(f"OpenAI client initialized via: {effective_base_url}")
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            raise

    async def _initialize_anthropic(self):
        """初始化 Anthropic 客户端"""
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
            raise

    async def _initialize_azure(self):
        """初始化 Azure OpenAI 客户端"""
        try:
            from openai import AsyncAzureOpenAI

            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.base_url,
                api_version="2024-02-01",
            )
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            raise

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> str:
        """
        生成文本（非流式）

        Args:
            prompt: 输入 Prompt
            temperature: 温度参数
            max_tokens: 最大 Token 数
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        if self.provider in ["openai", "azure"]:
            return await self._generate_openai(prompt, temperature, max_tokens, **kwargs)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, temperature, max_tokens, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_openai(
        self, prompt: str, temperature: float, max_tokens: int, **kwargs
    ) -> str:
        """OpenAI 生成"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return response.choices[0].message.content

    async def _generate_anthropic(
        self, prompt: str, temperature: float, max_tokens: int, **kwargs
    ) -> str:
        """Anthropic 生成"""
        response = await self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return response.content[0].text

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        生成文本（流式）

        Args:
            prompt: 输入 Prompt
            temperature: 温度参数
            max_tokens: 最大 Token 数

        Yields:
            文本块
        """
        if self.provider in ["openai", "azure"]:
            async for chunk in self._generate_stream_openai(
                prompt, temperature, max_tokens, **kwargs
            ):
                yield chunk
        elif self.provider == "anthropic":
            async for chunk in self._generate_stream_anthropic(
                prompt, temperature, max_tokens, **kwargs
            ):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_stream_openai(
        self, prompt: str, temperature: float, max_tokens: int, **kwargs
    ) -> AsyncIterator[str]:
        """OpenAI 流式生成"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _generate_stream_anthropic(
        self, prompt: str, temperature: float, max_tokens: int, **kwargs
    ) -> AsyncIterator[str]:
        """Anthropic 流式生成"""
        async with self.client.messages.stream(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _get_api_key_from_env(self) -> str:
        """从环境变量获取 API 密钥"""
        import os

        if self.provider == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        elif self.provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY", "")
        elif self.provider == "azure":
            return os.getenv("AZURE_OPENAI_API_KEY", "")
        return ""

    async def cleanup(self):
        """清理资源"""
        if self.client:
            # OpenAI/Anthropic 客户端无需显式关闭
            pass
        logger.info("LLM client cleaned up")
