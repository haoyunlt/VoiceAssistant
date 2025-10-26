"""
解析器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseParser(ABC):
    """文档解析器基类"""

    @abstractmethod
    async def parse(self, file_data: bytes, **kwargs) -> str:
        """
        解析文档

        Args:
            file_data: 文档二进制数据
            **kwargs: 额外参数

        Returns:
            解析后的文本内容
        """
        pass

    def extract_metadata(self, file_data: bytes) -> Dict:
        """
        提取文档元数据（可选实现）

        Args:
            file_data: 文档二进制数据

        Returns:
            元数据字典
        """
        return {}

    def clean_text(self, text: str) -> str:
        """
        清洗文本

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        # 移除多余空白
        text = " ".join(text.split())

        # 移除特殊字符（保留中英文、数字、常用标点）
        # 这里可以根据需要调整

        return text.strip()
