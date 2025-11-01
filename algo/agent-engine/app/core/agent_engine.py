"""
Agent Engine Core - 智能代理核心引擎
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.executor.plan_execute_executor import PlanExecuteExecutor
from app.core.executor.react_executor import ReActExecutor
from app.core.tools.tool_registry import ToolRegistry
from app.infrastructure.llm_client import LLMClient
from app.memory.unified_memory_manager import UnifiedMemoryManager

logger = logging.getLogger(__name__)


class AgentEngine:
    """Agent 引擎"""

    def __init__(self) -> None:
        """初始化 Agent 引擎"""
        # 核心组件
        self.llm_client = None
        self.tool_registry = None
        self.memory_manager = None
        self.executors: dict[str, Any] = {}

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_steps": 0,
            "total_tool_calls": 0,
            "avg_execution_time": 0,
            "total_execution_time": 0,
        }

        logger.info("Agent Engine created")

    async def initialize(self) -> None:
        """初始化所有组件"""
        logger.info("Initializing Agent Engine components...")

        # 初始化 LLM 客户端
        self.llm_client = LLMClient()
        await self.llm_client.initialize()  # type: ignore

        # 初始化工具注册表
        self.tool_registry = ToolRegistry()
        await self.tool_registry.initialize()  # type: ignore

        # 初始化记忆管理器
        self.memory_manager = UnifiedMemoryManager()
        await self.memory_manager.initialize()  # type: ignore

        # 初始化执行器
        from app.executors.reflexion_executor import ReflexionExecutor

        self.executors = {
            "react": ReActExecutor(self.llm_client, self.tool_registry),
            "plan_execute": PlanExecuteExecutor(self.llm_client, self.tool_registry),
            "reflexion": ReflexionExecutor(
                self.llm_client,  # type: ignore
                self.tool_registry,  # type: ignore
                self.memory_manager,  # type: ignore
                max_iterations=3,  # type: ignore
            ),
        }

        logger.info("Agent Engine initialized successfully")

    async def execute(
        self,
        task: str,
        mode: str = "react",
        max_steps: int = 10,
        tools: list[str] | None = None,
        conversation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """
        执行 Agent 任务（非流式）

        Args:
            task: 任务描述
            mode: 执行模式 (react/plan_execute)
            max_steps: 最大步骤数
            tools: 可用工具列表（None 表示全部）
            conversation_id: 会话 ID
            tenant_id: 租户 ID

        Returns:
            执行结果
        """
        if tools is None:
            tools = []
        start_time = time.time()
        self.stats["total_tasks"] += 1

        try:
            # 获取执行器
            executor = self.executors.get(mode)
            if not executor:
                raise ValueError(f"Unknown execution mode: {mode}")

            # 获取记忆（如果有）
            memory = None
            if conversation_id:
                memory = await self.memory_manager.recall_memories(conversation_id)  # type: ignore

            # 过滤工具
            available_tools = self._filter_tools(tools)

            # 执行任务
            result = await executor.execute(
                task=task,
                max_steps=max_steps,
                available_tools=available_tools,
                memory=memory,
            )

            # 更新记忆
            if conversation_id:
                await self.memory_manager.add_memory(  # type: ignore
                    user_id=tenant_id or "",
                    conversation_id=conversation_id,
                    content=task,
                    role="user",
                    metadata=None,
                )

            # 更新统计
            execution_time = time.time() - start_time
            self.stats["successful_tasks"] += 1
            self.stats["total_steps"] += result.get("step_count", 0)
            self.stats["total_tool_calls"] += result.get("tool_call_count", 0)
            self.stats["total_execution_time"] = int(execution_time)
            self.stats["avg_execution_time"] = (
                self.stats["total_execution_time"] / self.stats["successful_tasks"]  # type: ignore # noqa: E501
            )

            logger.info(f"Task executed successfully in {execution_time:.2f}s")

            return {
                **result,
                "task": task,
                "mode": mode,
                "execution_time": execution_time,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Error executing task: {e}", exc_info=True)
            raise

    async def execute_stream(
        self,
        task: str,
        mode: str = "react",
        max_steps: int = 10,
        tools: list[str] | None = None,
        conversation_id: str | None = None,
        _tenant_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        执行 Agent 任务（流式）

        Args:
            task: 任务描述
            mode: 执行模式
            max_steps: 最大步骤数
            tools: 可用工具列表
            conversation_id: 会话 ID
            tenant_id: 租户 ID

        Yields:
            JSON 格式的流式数据块
        """
        if tools is None:
            tools = []
        start_time = time.time()
        self.stats["total_tasks"] += 1

        try:
            # 获取执行器
            executor = self.executors.get(mode)
            if not executor:
                raise ValueError(f"Unknown execution mode: {mode}")

            # 获取记忆
            memory = None
            if conversation_id:
                memory = await self.memory_manager.recall_memories(conversation_id)  # type: ignore

            # 过滤工具
            available_tools = self._filter_tools(tools)

            # 流式执行
            final_result = None
            async for chunk in executor.execute_stream(
                task=task,
                max_steps=max_steps,
                available_tools=available_tools,
                memory=memory,
            ):
                # 如果是最终结果，保存
                chunk_data = json.loads(chunk)
                if chunk_data.get("type") == "final":
                    final_result = chunk_data.get("content")

                yield chunk

            # 更新记忆
            if conversation_id and final_result:
                await self.memory_manager.add_memory(  # type: ignore
                    conversation_id,
                    content=task,
                    role="user",
                    metadata=None,
                )

            # 发送完成信号
            execution_time = time.time() - start_time
            yield json.dumps(
                {
                    "type": "done",
                    "execution_time": execution_time,
                }
            )

            self.stats["successful_tasks"] += 1

        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Error in streaming execution: {e}", exc_info=True)

            yield json.dumps(
                {
                    "type": "error",
                    "content": str(e),
                }
            )

    def _filter_tools(self, tool_names: list[str] | None = None) -> list[dict]:
        """过滤可用工具"""
        all_tools = self.tool_registry.list_tools()  # type: ignore

        return [t for t in all_tools if t["name"] in tool_names]  # type: ignore

    async def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_tasks"]
                if self.stats["total_tasks"] > 0
                else 0
            ),
            "avg_steps_per_task": (
                self.stats["total_steps"] / self.stats["successful_tasks"]
                if self.stats["successful_tasks"] > 0
                else 0
            ),
            "avg_tool_calls_per_task": (
                self.stats["total_tool_calls"] / self.stats["successful_tasks"]
                if self.stats["successful_tasks"] > 0
                else 0
            ),
        }

    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Cleaning up Agent Engine...")

        if self.llm_client:
            await self.llm_client.cleanup()  # type: ignore

        if self.memory_manager:
            await self.memory_manager.cleanup()  # type: ignore

        logger.info("Agent Engine cleanup complete")
