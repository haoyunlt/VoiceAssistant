import logging
import os
from typing import Any, Dict, Optional

import httpx
from app.adapters.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

class AzureAdapter(BaseAdapter):
    """
    Azure OpenAI API 适配器。
    """

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
        self.client = httpx.AsyncClient(base_url=self.endpoint, timeout=30.0)

        # 价格表 (美元/1K tokens) - 与 OpenAI 相同
        self.pricing = {
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-35-turbo": {"input": 0.001, "output": 0.002},
            "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
        }

        logger.info("AzureAdapter initialized.")

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
        调用 Azure OpenAI Chat Completion API。
        """
        self.stats["total_requests"] += 1

        # Azure OpenAI 使用 deployment name 而不是 model name
        deployment_name = model

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        # Azure 的 URL 格式不同
        url = f"/openai/deployments/{deployment_name}/chat/completions?api-version={self.api_version}"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.debug(f"Calling Azure OpenAI API with deployment: {deployment_name}")
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()

            # 提取响应 (与 OpenAI 相同)
            message = data["choices"][0]["message"]
            text = message.get("content", "")
            finish_reason = data["choices"][0].get("finish_reason", "stop")

            # Token 使用量
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            # 计算成本 (使用模型名称获取价格)
            model_name = data.get("model", deployment_name)
            pricing = self.pricing.get(model_name, {"input": 0.01, "output": 0.03})
            cost_usd = (input_tokens / 1000.0 * pricing["input"]) + (output_tokens / 1000.0 * pricing["output"])

            self.stats["successful_requests"] += 1
            self.stats["total_tokens_used"] += total_tokens
            self.stats["total_cost_usd"] += cost_usd

            return {
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tokens_used": total_tokens,
                "cost_usd": cost_usd,
                "model": model_name,
                "finish_reason": finish_reason,
            }

        except httpx.HTTPStatusError as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Azure OpenAI API call failed: {e}", exc_info=True)
            raise RuntimeError(f"Azure OpenAI API call failed: {e}")
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Azure OpenAI API call failed: {e}", exc_info=True)
            raise RuntimeError(f"Azure OpenAI API call failed: {e}")

    async def embeddings(
        self,
        model: str,
        input: str | list[str],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用 Azure OpenAI Embeddings API。
        """
        self.stats["total_requests"] += 1

        deployment_name = model

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        url = f"/openai/deployments/{deployment_name}/embeddings?api-version={self.api_version}"

        payload = {
            "input": input,
        }

        try:
            logger.debug(f"Calling Azure OpenAI Embeddings API with deployment: {deployment_name}")
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()

            # 提取嵌入向量
            embeddings = [item["embedding"] for item in data["data"]]

            # Token 使用量
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            # 计算成本
            model_name = data.get("model", deployment_name)
            pricing = self.pricing.get(model_name, {"input": 0.0001, "output": 0.0})
            cost_usd = tokens_used / 1000.0 * pricing["input"]

            self.stats["successful_requests"] += 1
            self.stats["total_tokens_used"] += tokens_used
            self.stats["total_cost_usd"] += cost_usd

            return {
                "embeddings": embeddings,
                "model": model_name,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
            }

        except httpx.HTTPStatusError as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Azure OpenAI Embeddings API call failed: {e}", exc_info=True)
            raise RuntimeError(f"Azure OpenAI Embeddings API call failed: {e}")
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Azure OpenAI Embeddings API call failed: {e}", exc_info=True)
            raise RuntimeError(f"Azure OpenAI Embeddings API call failed: {e}")

    async def close(self):
        """关闭 HTTP 客户端连接"""
        if self.client:
            await self.client.aclose()
            logger.info("AzureAdapter HTTPX client closed.")
