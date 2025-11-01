"""
测试依赖注入
"""

import pytest
from app.api.dependencies import (
    get_agent_engine,
    get_memory_manager,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def test_get_agent_engine_not_initialized():
    """测试获取未初始化的 Agent Engine"""
    app = FastAPI()
    client = TestClient(app)

    @app.get("/test")
    async def test_route(request: Request):
        return get_agent_engine(request)

    with pytest.raises(Exception):  # noqa: B017
        response = client.get("/test")
        assert response.status_code == 503


def test_get_agent_engine_initialized():
    """测试获取已初始化的 Agent Engine"""
    app = FastAPI()

    # 模拟初始化
    class MockAgentEngine:
        def __init__(self):
            self.initialized = True

    app.state.agent_engine = MockAgentEngine()

    client = TestClient(app)

    @app.get("/test")
    async def test_route(request: Request):
        engine = get_agent_engine(request)
        return {"initialized": engine.initialized}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["initialized"] is True


def test_get_memory_manager_not_initialized():
    """测试获取未初始化的 Memory Manager"""
    app = FastAPI()
    client = TestClient(app)

    @app.get("/test")
    async def test_route(request: Request):
        return get_memory_manager(request)

    with pytest.raises(Exception):  # noqa: B017
        response = client.get("/test")
        assert response.status_code == 503
