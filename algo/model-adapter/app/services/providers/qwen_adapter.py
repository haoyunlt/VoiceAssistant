"""通义千问（Qwen）适配器"""
import json
import logging
from typing import Any, AsyncIterator, Dict

import httpx

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import ChatResponse, CompletionResponse, EmbeddingResponse, Usage
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class QwenAdapter(BaseAdapter):
    """通义千问适配器

    支持的模型：
    - qwen-turbo: 通义千问超大规模语言模型，支持8k上下文
    - qwen-plus: 通义千问增强版，支持32k上下文
    - qwen-max: 通义千问最强版本，支持30k上下文
    - qwen-max-longcontext: 支持超长上下文（30k tokens）
    - text-embedding-v1: 向量化模型
    """

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/api/v1"):
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
        logger.info(f"Qwen chat request: model={request.model}")

        # 构建请求体
        payload = self._build_chat_payload(request)

        try:
            response = await self.client.post("/services/aigc/text-generation/generation", json=payload)
            response.raise_for_status()
            data = response.json()

            # 转换响应格式
            return self._parse_chat_response(data, request.model)

        except httpx.HTTPError as e:
            logger.error(f"Qwen API error: {e}")
            raise Exception(f"Qwen API request failed: {str(e)}")

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        logger.info(f"Qwen streaming chat request: model={request.model}")

        # 构建请求体（启用流式）
        payload = self._build_chat_payload(request)
        payload["parameters"]["incremental_output"] = True

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable"  # 启用SSE
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/services/aigc/text-generation/generation",
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "":
                            continue

                        if line.startswith("data:"):
                            line = line[5:].strip()  # 移除 "data:" 前缀

                        if not line:
                            continue

                        try:
                            chunk_data = json.loads(line)
                            # 转换为OpenAI格式
                            openai_chunk = self._convert_to_openai_stream_format(chunk_data)

                            if openai_chunk:
                                yield f"data: {json.dumps(openai_chunk)}\n\n"

                            # 检查是否完成
                            if chunk_data.get("output", {}).get("finish_reason"):
                                yield "data: [DONE]\n\n"
                                break

                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse stream chunk: {line}")
                            continue

        except httpx.HTTPError as e:
            logger.error(f"Qwen streaming API error: {e}")
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "api_error"
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口（通义千问使用chat接口实现）"""
        logger.info(f"Qwen completion request: model={request.model}")

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
        logger.info(f"Qwen embedding request: model={request.model}")

        # 通义千问的embedding接口
        payload = {
            "model": request.model or "text-embedding-v1",
            "input": {
                "texts": request.input if isinstance(request.input, list) else [request.input]
            },
            "parameters": {
                "text_type": "document"  # document或query
            }
        }

        try:
            response = await self.client.post("/services/embeddings/text-embedding/text-embedding", json=payload)
            response.raise_for_status()
            data = response.json()

            # 转换响应格式
            output_data = data.get("output", {})
            embeddings_data = output_data.get("embeddings", [])
            usage_data = data.get("usage", {})

            return EmbeddingResponse(
                object="list",
                model=request.model or "text-embedding-v1",
                data=[
                    {
                        "object": "embedding",
                        "index": i,
                        "embedding": item.get("embedding", [])
                    }
                    for i, item in enumerate(embeddings_data)
                ],
                usage=Usage(
                    prompt_tokens=usage_data.get("total_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                )
            )

        except httpx.HTTPError as e:
            logger.error(f"Qwen embedding API error: {e}")
            raise Exception(f"Qwen embedding request failed: {str(e)}")

    def _build_chat_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """构建通义千问聊天请求体"""
        # 通义千问使用不同的请求格式
        payload = {
            "model": request.model,
            "input": {
                "messages": request.messages
            },
            "parameters": {}
        }

        # 可选参数
        if request.temperature is not None:
            payload["parameters"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["parameters"]["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["parameters"]["top_p"] = request.top_p
        if request.stop:
            payload["parameters"]["stop"] = request.stop

        # 通义千问特有参数
        if hasattr(request, "enable_search") and request.enable_search:
            payload["parameters"]["enable_search"] = True
        if hasattr(request, "tools") and request.tools:
            payload["parameters"]["tools"] = request.tools

        return payload

    def _parse_chat_response(self, data: Dict[str, Any], model: str) -> ChatResponse:
        """解析通义千问聊天响应"""
        output_data = data.get("output", {})
        usage_data = data.get("usage", {})
        request_id = data.get("request_id", "")

        # 通义千问的响应格式
        text = output_data.get("text", "")
        finish_reason = output_data.get("finish_reason", "stop")

        return ChatResponse(
            id=request_id,
            object="chat.completion",
            created=0,  # 通义千问不返回时间戳
            model=model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text
                    },
                    "finish_reason": finish_reason
                }
            ],
            usage=Usage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )
        )

    def _convert_to_openai_stream_format(self, qwen_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """将通义千问流式响应转换为OpenAI格式"""
        output_data = qwen_chunk.get("output", {})
        request_id = qwen_chunk.get("request_id", "")

        text = output_data.get("text", "")
        finish_reason = output_data.get("finish_reason")

        if not text and not finish_reason:
            return None

        return {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant" if text else None,
                        "content": text
                    },
                    "finish_reason": finish_reason
                }
            ]
        }

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
