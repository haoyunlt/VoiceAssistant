"""
Agent执行器策略模式
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class ExecutorStrategy(ABC):
    """执行器策略接口"""

    @abstractmethod
    async def execute(
        self,
        task: str,
        max_steps: int,
        available_tools: list[dict],
        memory: dict | None = None,
    ) -> dict:
        """
        执行任务（非流式）

        Args:
            task: 任务描述
            max_steps: 最大步骤数
            available_tools: 可用工具列表
            memory: 记忆（可选）

        Returns:
            执行结果
        """
        pass

    @abstractmethod
    async def execute_stream(
        self,
        task: str,
        max_steps: int,
        available_tools: list[dict],
        memory: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        执行任务（流式）

        Args:
            task: 任务描述
            max_steps: 最大步骤数
            available_tools: 可用工具列表
            memory: 记忆（可选）

        Yields:
            JSON 格式的流式数据块
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取执行器名称"""
        pass


class ExecutorFactory:
    """执行器工厂"""

    def __init__(self) -> None:
        self._executors: dict[str, ExecutorStrategy] = {}

    def register(self, name: str, executor: ExecutorStrategy) -> None:
        """注册执行器"""
        self._executors[name] = executor

    def get(self, name: str) -> ExecutorStrategy | None:
        """获取执行器"""
        return self._executors.get(name)

    def list_available(self) -> list[str]:
        """列出可用的执行器"""
        return list(self._executors.keys())

    def has(self, name: str) -> bool:
        """检查执行器是否存在"""
        return name in self._executors


class ExecutorContext:
    """执行器上下文（策略模式）"""

    def __init__(self, factory: ExecutorFactory):
        self._factory = factory
        self._current_strategy: ExecutorStrategy | None = None

    def set_strategy(self, strategy_name: str) -> None:
        """设置当前策略"""
        strategy = self._factory.get(strategy_name)
        if strategy is None:
            raise ValueError(f"Unknown executor strategy: {strategy_name}")
        self._current_strategy = strategy

    async def execute(
        self,
        task: str,
        max_steps: int,
        available_tools: list[dict],
        memory: dict | None = None,
    ) -> dict:
        """执行任务"""
        if self._current_strategy is None:
            raise RuntimeError("No strategy set")

        return await self._current_strategy.execute(
            task, max_steps, available_tools, memory
        )

    async def execute_stream(
        self,
        task: str,
        max_steps: int,
        available_tools: list[dict],
        memory: dict | None = None,
    ) -> AsyncIterator[str]:
        """执行任务（流式）"""
        if self._current_strategy is None:
            raise RuntimeError("No strategy set")

        async for chunk in self._current_strategy.execute_stream(  # type: ignore
            task, max_steps, available_tools, memory
        ):
            yield chunk
