"""Pytest配置文件."""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def anyio_backend():
    """设置anyio后端."""
    return "asyncio"
