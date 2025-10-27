"""
Agent Engine V2 - 使用依赖注入和策略模式
"""

import logging
import time
from typing import AsyncIterator, Dict, List, Optional

from app.core.config import AgentConfig
from app.core.executor_strategy import ExecutorContext, ExecutorFactory
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.memory_manager import MemoryManager
from app.infrastructure.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentEngineV2:
    """Agent 引擎 V2 - 重构版"""

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        memory_manager: Optional[MemoryManager] = None,
        executor_factory: Optional[ExecutorFactory] = None,
    ):
        """
        初始化 Agent 引擎（依赖注入）

        Args:
            config: 配置对象
            llm_client: LLM客户端
            tool_registry: 工具注册表
            memory_manager: 记忆管理器（可选）
            executor_factory: 执行器工厂（可选）
        """
        self.config = config
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.memory_manager = memory_manager

        # 执行器上下文
        if executor_factory is None:
            executor_factory = self._create_default_factory()

        self.executor_context = ExecutorContext(executor_factory)

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_steps": 0,
            "total_tool_calls": 0,
            "avg_execution_time": 0.0,
            "total_execution_time": 0.0,
        }

        logger.info("Agent Engine V2 initialized with dependency injection")

    def _create_default_factory(self) -> ExecutorFactory:
        """创建默认的执行器工厂"""
        from app.core.executor.plan_execute_executor import PlanExecuteExecutor
        from app.core.executor.react_executor import ReActExecutor

        factory = ExecutorFactory()

        # 注册默认执行器
        factory.register(
            "react", ReActExecutor(self.llm_client, self.tool_registry)
        )
        factory.register(
            "plan_execute",
            PlanExecuteExecutor(self.llm_client, self.tool_registry),
        )

        # 如果启用了 Reflexion，注册 Reflexion 执行器
        if self.config.enable_reflexion and self.memory_manager:
            from app.executors.reflexion_executor import ReflexionExecutor

            factory.register(
                "reflexion",
                ReflexionExecutor(
                    self.llm_client,
                    self.tool_registry,
                    self.memory_manager,
                    max_iterations=self.config.max_iterations,
                ),
            )

        return factory

    async def execute(
        self,
        task: str,
        mode: Optional[str] = None,
        max_steps: Optional[int] = None,
        tools: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict:
        """
        执行 Agent 任务（非流式）

        Args:
            task: 任务描述
            mode: 执行模式 (react/plan_execute/reflexion)
            max_steps: 最大步骤数
            tools: 可用工具列表（None 表示全部）
            conversation_id: 会话 ID
            tenant_id: 租户 ID

        Returns:
            执行结果
        """
        start_time = time.time()
        self.stats["total_tasks"] += 1

        # 使用配置的默认值
        if mode is None:
            mode = self.config.default_mode
        if max_steps is None:
            max_steps = self.config.max_steps

        try:
            # 设置执行策略
            self.executor_context.set_strategy(mode)

            # 获取记忆（如果启用）
            memory = None
            if self.config.memory_enabled and conversation_id and self.memory_manager:
                memory = await self.memory_manager.get_memory(conversation_id)

            # 过滤工具
            available_tools = self._filter_tools(tools)

            # 执行任务
            result = await self.executor_context.execute(
                task=task,
                max_steps=max_steps,
                available_tools=available_tools,
                memory=memory,
            )

            # 更新记忆
            if (
                self.config.memory_enabled
                and conversation_id
                and self.memory_manager
            ):
                await self.memory_manager.add_to_memory(
                    conversation_id,
                    task=task,
                    result=result,
                )

            # 更新统计
            execution_time = time.time() - start_time
            self._update_stats(result, execution_time, success=True)

            logger.info(f"Task executed successfully in {execution_time:.2f}s")

            return {
                **result,
                "task": task,
                "mode": mode,
                "execution_time": execution_time,
                "conversation_id": conversation_id,
                "tenant_id": tenant_id,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats({}, execution_time, success=False)
            logger.error(f"Error executing task: {e}", exc_info=True)
            raise

    async def execute_stream(
        self,
        task: str,
        mode: Optional[str] = None,
        max_steps: Optional[int] = None,
        tools: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
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
        import json

        start_time = time.time()
        self.stats["total_tasks"] += 1

        # 使用配置的默认值
        if mode is None:
            mode = self.config.default_mode
        if max_steps is None:
            max_steps = self.config.max_steps

        try:
            # 设置执行策略
            self.executor_context.set_strategy(mode)

            # 获取记忆
            memory = None
            if self.config.memory_enabled and conversation_id and self.memory_manager:
                memory = await self.memory_manager.get_memory(conversation_id)

            # 过滤工具
            available_tools = self._filter_tools(tools)

            # 流式执行
            final_result = None
            async for chunk in self.executor_context.execute_stream(
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
            if (
                self.config.memory_enabled
                and conversation_id
                and final_result
                and self.memory_manager
            ):
                await self.memory_manager.add_to_memory(
                    conversation_id,
                    task=task,
                    result=final_result,
                )

            # 发送完成信号
            execution_time = time.time() - start_time
            yield json.dumps(
                {
                    "type": "done",
                    "execution_time": execution_time,
                    "mode": mode,
                    "conversation_id": conversation_id,
                }
            )

            self.stats["successful_tasks"] += 1

        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Error in streaming execution: {e}", exc_info=True)

            import json

            yield json.dumps(
                {
                    "type": "error",
                    "content": str(e),
                }
            )

    def _filter_tools(self, tool_names: Optional[List[str]]) -> List[Dict]:
        """过滤可用工具"""
        all_tools = self.tool_registry.list_tools()

        if tool_names is None:
            if self.config.enable_all_tools:
                return all_tools
            else:
                # 返回默认工具集
                return [t for t in all_tools if t.get("is_default", False)]

        return [t for t in all_tools if t["name"] in tool_names]

    def _update_stats(
        self, result: Dict, execution_time: float, success: bool
    ) -> None:
        """更新统计信息"""
        if success:
            self.stats["successful_tasks"] += 1
            self.stats["total_steps"] += result.get("step_count", 0)
            self.stats["total_tool_calls"] += result.get("tool_call_count", 0)
        else:
            self.stats["failed_tasks"] += 1

        self.stats["total_execution_time"] += execution_time
        if self.stats["successful_tasks"] > 0:
            self.stats["avg_execution_time"] = (
                self.stats["total_execution_time"] / self.stats["successful_tasks"]
            )

    async def get_stats(self) -> Dict:
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

    def list_available_executors(self) -> List[str]:
        """列出可用的执行器"""
        return self.executor_context._factory.list_available()
