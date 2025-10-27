"""
RAG Engine 专用LLM客户端配置
使用统一的UnifiedLLMClient
"""

import os
import sys
from pathlib import Path

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

from llm_client import UnifiedLLMClient


def get_rag_llm_client() -> UnifiedLLMClient:
    """获取RAG Engine的LLM客户端"""
    return UnifiedLLMClient(
        model_adapter_url=os.getenv(
            "MODEL_ADAPTER_URL", "http://model-adapter:8005"
        ),
        timeout=60,
        default_model=os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo"),
    )
