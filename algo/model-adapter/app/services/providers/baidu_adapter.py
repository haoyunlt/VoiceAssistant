"""百度文心一言（ERNIE）适配器"""
import json
import logging
import time
from typing import Any, AsyncIterator, Dict

import httpx

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import ChatResponse, CompletionResponse, EmbeddingResponse, Usage
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class BaiduAdapter(BaseAdapter):
    """百度文心一言适配器

    支持的模型：
    - ERNIE-Bot-4: 文心大模型4.0，最强版本
    - ERNIE-Bot: 文心大模型，平衡性能和效果
    - ERNIE-Bot-turbo: 文心大模型，高性能版本
    - ERNIE-Speed: 文心快速版，适合简单场景
    - Embedding-V1: 向量化模型
    """

    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://aip.baidubce.com"):
        """初始化百度文心适配器

        Args:
            api_key: API Key
            secret_key: Secret Key
            base_url: API基础URL
        """
        super().__init__(api_key, base_url)
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0
        self.client = httpx.AsyncClient(timeout=60.0)

    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        # 检查token是否过期
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # 获取新token
        url = f"{self.base_url}/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in", 2592000)  # 默认30天
            self.token_expires_at = time.time() + expires_in - 60  # 提前1分钟刷新

            logger.info("Successfully obtained Baidu access token")
            return self.access_token

        except Exception as e:
            logger.error(f"Failed to get Baidu access token: {e}")
            raise Exception(f"Failed to authenticate with Baidu API: {str(e)}")

    def _get_model_endpoint(self, model: str) -> str:
        """获取模型对应的endpoint"""
        model_endpoints = {
            "ERNIE-Bot-4": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
            "ERNIE-Bot": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            "ERNIE-Bot-turbo": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant",
            "ERNIE-Speed": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie_speed",
            "ERNIE-Bot-8K": "/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie_bot_8k"
        }
        return model_endpoints.get(model, model_endpoints["ERNIE-Bot"])

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        logger.info(f"Baidu chat request: model={request.model}")

        # 获取access token
        access_token = await self._get_access_token()

        # 构建请求体
        payload = self._build_chat_payload(request)

        # 获取模型endpoint
        endpoint = self._get_model_endpoint(request.model)
        url = f"{self.base_url}{endpoint}?access_token={access_token}"

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # 检查错误
            if "error_code" in data:
                raise Exception(f"Baidu API error: {data.get('error_msg', 'Unknown error')}")

            # 转换响应格式
            return self._parse_chat_response(data, request.model)

        except httpx.HTTPError as e:
            logger.error(f"Baidu API error: {e}")
            raise Exception(f"Baidu API request failed: {str(e)}")

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        logger.info(f"Baidu streaming chat request: model={request.model}")

        # 获取access token
        access_token = await self._get_access_token()

        # 构建请求体（启用流式）
        payload = self._build_chat_payload(request)
        payload["stream"] = True

        # 获取模型endpoint
        endpoint = self._get_model_endpoint(request.model)
        url = f"{self.base_url}{endpoint}?access_token={access_token}"

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue

                    if line.startswith("data: "):
                        line = line[6:]  # 移除 "data: " 前缀

                    try:
                        chunk_data = json.loads(line)

                        # 检查错误
                        if "error_code" in chunk_data:
                            error_data = {
                                "error": {
                                    "message": chunk_data.get("error_msg", "Unknown error"),
                                    "type": "api_error"
                                }
                            }
                            yield f"data: {json.dumps(error_data)}\n\n"
                            break

                        # 转换为OpenAI格式
                        openai_chunk = self._convert_to_openai_stream_format(chunk_data)

                        if openai_chunk:
                            yield f"data: {json.dumps(openai_chunk)}\n\n"

                        # 检查是否完成
                        if chunk_data.get("is_end", False):
                            yield "data: [DONE]\n\n"
                            break

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse stream chunk: {line}")
                        continue

        except httpx.HTTPError as e:
            logger.error(f"Baidu streaming API error: {e}")
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "api_error"
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口（百度文心使用chat接口实现）"""
        logger.info(f"Baidu completion request: model={request.model}")

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
        logger.info(f"Baidu embedding request: model={request.model}")

        # 获取access token
        access_token = await self._get_access_token()

        # 百度文心的embedding接口
        url = f"{self.base_url}/rpc/2.0/ai_custom/v1/wenxinworkshop/embeddings/embedding-v1?access_token={access_token}"

        payload = {
            "input": request.input if isinstance(request.input, list) else [request.input]
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # 检查错误
            if "error_code" in data:
                raise Exception(f"Baidu API error: {data.get('error_msg', 'Unknown error')}")

            # 转换响应格式
            embeddings_data = data.get("data", [])
            usage_data = data.get("usage", {})

            return EmbeddingResponse(
                object="list",
                model=request.model or "Embedding-V1",
                data=[
                    {
                        "object": "embedding",
                        "index": i,
                        "embedding": item.get("embedding", [])
                    }
                    for i, item in enumerate(embeddings_data)
                ],
                usage=Usage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0)
                )
            )

        except httpx.HTTPError as e:
            logger.error(f"Baidu embedding API error: {e}")
            raise Exception(f"Baidu embedding request failed: {str(e)}")

    def _build_chat_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """构建百度文心聊天请求体"""
        payload = {
            "messages": request.messages
        }

        # 可选参数
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        # 百度文心特有参数
        if hasattr(request, "penalty_score") and request.penalty_score:
            payload["penalty_score"] = request.penalty_score
        if hasattr(request, "functions") and request.functions:
            payload["functions"] = request.functions

        return payload

    def _parse_chat_response(self, data: Dict[str, Any], model: str) -> ChatResponse:
        """解析百度文心聊天响应"""
        result = data.get("result", "")
        usage_data = data.get("usage", {})
        request_id = data.get("id", "")

        # 百度文心特有的完成原因
        finish_reason_map = {
            "normal": "stop",
            "stop": "stop",
            "length": "length",
            "content_filter": "content_filter"
        }
        finish_reason = finish_reason_map.get(data.get("finish_reason", "normal"), "stop")

        return ChatResponse(
            id=request_id,
            object="chat.completion",
            created=data.get("created", int(time.time())),
            model=model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result,
                        "function_call": data.get("function_call")
                    },
                    "finish_reason": finish_reason
                }
            ],
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )
        )

    def _convert_to_openai_stream_format(self, baidu_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """将百度文心流式响应转换为OpenAI格式"""
        result = baidu_chunk.get("result", "")
        is_end = baidu_chunk.get("is_end", False)
        request_id = baidu_chunk.get("id", "")

        if not result and not is_end:
            return None

        finish_reason = None
        if is_end:
            finish_reason_map = {
                "normal": "stop",
                "stop": "stop",
                "length": "length",
                "content_filter": "content_filter"
            }
            finish_reason = finish_reason_map.get(baidu_chunk.get("finish_reason", "normal"), "stop")

        return {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": baidu_chunk.get("created", int(time.time())),
            "model": "",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant" if result else None,
                        "content": result
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
