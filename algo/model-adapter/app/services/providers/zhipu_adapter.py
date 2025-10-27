"""智谱AI GLM-4适配器"""
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import ChatResponse, CompletionResponse, EmbeddingResponse, Usage
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class ZhipuAdapter(BaseAdapter):
    """智谱AI GLM-4适配器

    支持的模型：
    - glm-4: 最新的GLM-4模型
    - glm-4v: 支持视觉的多模态模型
    - glm-3-turbo: GLM-3 Turbo模型
    - embedding-2: 向量化模型
    """

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4"):
        super().__init__(api_key, base_url)
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        logger.info(f"Zhipu chat request: model={request.model}")

        # 构建请求体
        payload = self._build_chat_payload(request)

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # 转换响应格式
            return self._parse_chat_response(data, request.model)

        except httpx.HTTPError as e:
            logger.error(f"Zhipu API error: {e}")
            raise Exception(f"Zhipu API request failed: {str(e)}")

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        logger.info(f"Zhipu streaming chat request: model={request.model}")

        # 构建请求体（启用流式）
        payload = self._build_chat_payload(request)
        payload["stream"] = True

        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]  # 移除 "data: " 前缀

                    if line.strip() == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break

                    try:
                        chunk_data = json.loads(line)
                        # 转换为OpenAI格式
                        openai_chunk = self._convert_to_openai_stream_format(chunk_data)
                        yield f"data: {json.dumps(openai_chunk)}\n\n"
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse stream chunk: {line}")
                        continue

        except httpx.HTTPError as e:
            logger.error(f"Zhipu streaming API error: {e}")
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "api_error"
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口（智谱AI使用chat接口实现）"""
        logger.info(f"Zhipu completion request: model={request.model}")

        # 将completion请求转换为chat请求
        chat_request = ChatRequest(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stop=request.stop
        )

        chat_response = await self.chat(chat_request)

        # 转换为CompletionResponse
        return CompletionResponse(
            id=chat_response.id,
            object="text_completion",
            created=chat_response.created,
            model=chat_response.model,
            choices=[{
                "text": chat_response.choices[0]["message"]["content"],
                "index": 0,
                "finish_reason": chat_response.choices[0]["finish_reason"]
            }],
            usage=chat_response.usage
        )

    async def completion_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """流式补全接口"""
        # 将completion请求转换为chat请求
        chat_request = ChatRequest(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stop=request.stop
        )

        async for chunk in self.chat_stream(chat_request):
            yield chunk

    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """向量化接口"""
        logger.info(f"Zhipu embedding request: model={request.model}")

        # 智谱AI的embedding接口
        payload = {
            "model": request.model or "embedding-2",
            "input": request.input if isinstance(request.input, list) else [request.input]
        }

        try:
            response = await self.client.post("/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()

            # 转换响应格式
            return EmbeddingResponse(
                object="list",
                model=data.get("model", request.model),
                data=[
                    {
                        "object": "embedding",
                        "index": i,
                        "embedding": item["embedding"]
                    }
                    for i, item in enumerate(data.get("data", []))
                ],
                usage=Usage(
                    prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                    total_tokens=data.get("usage", {}).get("total_tokens", 0)
                )
            )

        except httpx.HTTPError as e:
            logger.error(f"Zhipu embedding API error: {e}")
            raise Exception(f"Zhipu embedding request failed: {str(e)}")

    def _build_chat_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """构建智谱AI聊天请求体"""
        payload = {
            "model": request.model,
            "messages": request.messages
        }

        # 可选参数
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop"] = request.stop

        # 智谱AI特有参数
        if hasattr(request, "tools") and request.tools:
            payload["tools"] = request.tools
        if hasattr(request, "tool_choice") and request.tool_choice:
            payload["tool_choice"] = request.tool_choice

        return payload

    def _parse_chat_response(self, data: Dict[str, Any], model: str) -> ChatResponse:
        """解析智谱AI聊天响应"""
        choices = data.get("choices", [])
        usage_data = data.get("usage", {})

        return ChatResponse(
            id=data.get("id", ""),
            object="chat.completion",
            created=data.get("created", 0),
            model=model,
            choices=[
                {
                    "index": choice.get("index", 0),
                    "message": {
                        "role": choice.get("message", {}).get("role", "assistant"),
                        "content": choice.get("message", {}).get("content", ""),
                        "tool_calls": choice.get("message", {}).get("tool_calls")
                    },
                    "finish_reason": choice.get("finish_reason", "stop")
                }
                for choice in choices
            ],
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )
        )

    def _convert_to_openai_stream_format(self, zhipu_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """将智谱AI流式响应转换为OpenAI格式"""
        choices = zhipu_chunk.get("choices", [])

        return {
            "id": zhipu_chunk.get("id", ""),
            "object": "chat.completion.chunk",
            "created": zhipu_chunk.get("created", 0),
            "model": zhipu_chunk.get("model", ""),
            "choices": [
                {
                    "index": choice.get("index", 0),
                    "delta": {
                        "role": choice.get("delta", {}).get("role"),
                        "content": choice.get("delta", {}).get("content", "")
                    },
                    "finish_reason": choice.get("finish_reason")
                }
                for choice in choices
            ]
        }

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
