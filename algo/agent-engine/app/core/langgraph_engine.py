"""
LangGraph Workflow Engine - 动态工作流引擎

实现功能：
- 动态工作流创建（基于JSON配置）
- 状态持久化（Redis Checkpoint）
- 工作流可恢复（中断后继续）
- 条件分支
- 子图支持
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """节点类型"""

    ACTION = "action"  # 动作节点
    DECISION = "decision"  # 决策节点
    PARALLEL = "parallel"  # 并行节点
    SUBGRAPH = "subgraph"  # 子图节点


class ExecutionStatus(Enum):
    """执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowState:
    """工作流状态"""

    workflow_id: str
    current_node: str
    node_history: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error: str | None = None


@dataclass
class WorkflowNode:
    """工作流节点"""

    node_id: str
    node_type: NodeType
    function: Callable | None = None
    condition: Callable | None = None  # 条件函数（决策节点）
    next_nodes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """
    Checkpoint管理器（状态持久化）

    用法:
        manager = CheckpointManager(redis_client)

        # 保存checkpoint
        await manager.save_checkpoint(workflow_id, state)

        # 加载checkpoint
        state = await manager.load_checkpoint(workflow_id)
    """

    def __init__(self, redis_client: Any | None = None):
        self.redis_client = redis_client
        self.local_checkpoints: dict[str, WorkflowState] = {}

        logger.info(
            f"CheckpointManager initialized (storage={'redis' if redis_client else 'local'})"
        )

    async def save_checkpoint(self, workflow_id: str, state: WorkflowState):
        """保存checkpoint"""
        state.updated_at = datetime.now()

        if self.redis_client:
            # 保存到Redis
            key = f"workflow:checkpoint:{workflow_id}"
            value = json.dumps(
                {
                    "workflow_id": state.workflow_id,
                    "current_node": state.current_node,
                    "node_history": state.node_history,
                    "variables": state.variables,
                    "status": state.status.value,
                    "created_at": state.created_at.isoformat(),
                    "updated_at": state.updated_at.isoformat(),
                    "error": state.error,
                }
            )

            await self.redis_client.set(key, value, ex=86400)  # 24小时过期
            logger.debug(f"Checkpoint saved to Redis: {workflow_id}")
        else:
            # 本地存储
            self.local_checkpoints[workflow_id] = state
            logger.debug(f"Checkpoint saved locally: {workflow_id}")

    async def load_checkpoint(self, workflow_id: str) -> WorkflowState | None:
        """加载checkpoint"""
        if self.redis_client:
            # 从Redis加载
            key = f"workflow:checkpoint:{workflow_id}"
            value = await self.redis_client.get(key)

            if value:
                data = json.loads(value)
                return WorkflowState(
                    workflow_id=data["workflow_id"],
                    current_node=data["current_node"],
                    node_history=data["node_history"],
                    variables=data["variables"],
                    status=ExecutionStatus(data["status"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"]),
                    error=data.get("error"),
                )
        else:
            # 从本地加载
            return self.local_checkpoints.get(workflow_id)

        return None

    async def delete_checkpoint(self, workflow_id: str):
        """删除checkpoint"""
        if self.redis_client:
            key = f"workflow:checkpoint:{workflow_id}"
            await self.redis_client.delete(key)
        else:
            self.local_checkpoints.pop(workflow_id, None)

        logger.debug(f"Checkpoint deleted: {workflow_id}")


class LangGraphWorkflowEngine:
    """
    LangGraph工作流引擎

    用法:
        engine = LangGraphWorkflowEngine(checkpoint_manager)

        # 创建工作流
        workflow = engine.create_workflow({
            "nodes": [
                {"id": "start", "type": "action", "function": "analyze_task"},
                {"id": "retrieve", "type": "action", "function": "retrieve_documents"},
                {"id": "decide", "type": "decision", "condition": "needs_review"},
                {"id": "review", "type": "action", "function": "review_result"},
                {"id": "end", "type": "action", "function": "finalize"}
            ],
            "edges": [
                {"from": "start", "to": "retrieve"},
                {"from": "retrieve", "to": "decide"},
                {"from": "decide", "to": {"review": "needs_review", "end": "else"}},
                {"from": "review", "to": "end"}
            ],
            "entry": "start"
        })

        # 执行工作流
        result = await engine.execute(workflow_id, initial_data)

        # 中断后恢复执行
        result = await engine.resume(workflow_id)
    """

    def __init__(
        self,
        checkpoint_manager: CheckpointManager | None = None,
        function_registry: dict[str, Callable] | None = None,
    ):
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.function_registry = function_registry or {}

        # 工作流定义存储
        self.workflows: dict[str, dict[str, WorkflowNode]] = {}

        # 统计信息
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "resumed_executions": 0,
        }

        logger.info("LangGraphWorkflowEngine initialized")

    def create_workflow(self, config: dict) -> str:
        """
        动态创建工作流

        Args:
            config: 工作流配置
                {
                    "nodes": [{"id": "...", "type": "...", "function": "..."}],
                    "edges": [{"from": "...", "to": "..."}],
                    "entry": "start_node_id"
                }

        Returns:
            workflow_id: 工作流ID
        """
        workflow_id = f"wf_{datetime.now().timestamp()}"

        # 解析节点
        nodes: dict[str, WorkflowNode] = {}
        for node_config in config["nodes"]:
            node_id = node_config["id"]
            node_type = NodeType(node_config["type"])

            # 解析函数
            function = None
            if "function" in node_config:
                func_name = node_config["function"]
                function = self.function_registry.get(func_name)
                if not function:
                    logger.warning(f"Function {func_name} not found in registry")

            # 解析条件
            condition = None
            if "condition" in node_config:
                cond_name = node_config["condition"]
                condition = self.function_registry.get(cond_name)

            nodes[node_id] = WorkflowNode(
                node_id=node_id,
                node_type=node_type,
                function=function,
                condition=condition,
                metadata=node_config.get("metadata", {}),
            )

        # 解析边
        for edge_config in config["edges"]:
            from_node_id = edge_config["from"]
            to_node = edge_config["to"]

            if from_node_id in nodes:
                if isinstance(to_node, dict):
                    # 条件边
                    nodes[from_node_id].next_nodes = list(to_node.values())
                    nodes[from_node_id].metadata["conditional_next"] = to_node
                else:
                    # 普通边
                    nodes[from_node_id].next_nodes.append(to_node)

        # 保存工作流定义
        self.workflows[workflow_id] = nodes

        logger.info(
            f"Workflow created: {workflow_id} ({len(nodes)} nodes, entry={config['entry']})"
        )

        return workflow_id

    async def execute(
        self,
        workflow_id: str,
        initial_data: dict[str, Any],
        entry_node: str = "start",
        save_checkpoints: bool = True,
    ) -> dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流ID
            initial_data: 初始数据
            entry_node: 入口节点
            save_checkpoints: 是否保存checkpoint

        Returns:
            执行结果
        """
        self.stats["total_executions"] += 1

        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        # 创建初始状态
        state = WorkflowState(
            workflow_id=workflow_id,
            current_node=entry_node,
            variables=initial_data,
            status=ExecutionStatus.RUNNING,
        )

        # 保存初始checkpoint
        if save_checkpoints:
            await self.checkpoint_manager.save_checkpoint(workflow_id, state)

        # 执行工作流
        try:
            result = await self._execute_workflow(workflow_id, state, save_checkpoints)

            self.stats["successful_executions"] += 1
            return result

        except Exception as e:
            self.stats["failed_executions"] += 1
            state.status = ExecutionStatus.FAILED
            state.error = str(e)

            if save_checkpoints:
                await self.checkpoint_manager.save_checkpoint(workflow_id, state)

            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            raise

    async def resume(self, workflow_id: str) -> dict[str, Any]:
        """
        恢复工作流执行

        Args:
            workflow_id: 工作流ID

        Returns:
            执行结果
        """
        # 加载checkpoint
        state = await self.checkpoint_manager.load_checkpoint(workflow_id)

        if not state:
            raise ValueError(f"No checkpoint found for workflow {workflow_id}")

        if state.status == ExecutionStatus.COMPLETED:
            logger.info(f"Workflow {workflow_id} already completed")
            return {"status": "completed", "variables": state.variables}

        logger.info(f"Resuming workflow {workflow_id} from node {state.current_node}")

        self.stats["resumed_executions"] += 1
        state.status = ExecutionStatus.RUNNING

        # 继续执行
        return await self._execute_workflow(workflow_id, state, save_checkpoints=True)

    async def _execute_workflow(
        self, workflow_id: str, state: WorkflowState, save_checkpoints: bool
    ) -> dict[str, Any]:
        """执行工作流（内部方法）"""
        nodes = self.workflows[workflow_id]

        while state.current_node:
            # 获取当前节点
            node = nodes.get(state.current_node)
            if not node:
                raise ValueError(f"Node {state.current_node} not found")

            logger.debug(f"Executing node: {node.node_id} (type={node.node_type.value})")

            # 记录历史
            state.node_history.append(node.node_id)

            # 执行节点
            try:
                if node.node_type == NodeType.ACTION:
                    # 动作节点
                    if node.function:
                        result = await self._execute_function(node.function, state.variables)
                        state.variables.update(result)

                elif node.node_type == NodeType.DECISION:
                    # 决策节点
                    if node.condition:
                        decision = await self._execute_function(node.condition, state.variables)
                        state.variables["_last_decision"] = decision

                elif node.node_type == NodeType.PARALLEL:  # noqa: SIM102
                    # 并行节点
                    if node.function:
                        results = await self._execute_parallel(node.function, state.variables)
                        state.variables.update(results)

                # 保存checkpoint
                if save_checkpoints:
                    await self.checkpoint_manager.save_checkpoint(workflow_id, state)

                # 获取下一个节点
                next_node = self._get_next_node(node, state.variables)

                if not next_node:
                    # 工作流结束
                    state.status = ExecutionStatus.COMPLETED
                    state.current_node = ""
                    break

                state.current_node = next_node

            except Exception as e:
                logger.error(f"Node execution failed: {node.node_id}, error: {e}")
                raise

        # 最终checkpoint
        if save_checkpoints:
            await self.checkpoint_manager.save_checkpoint(workflow_id, state)

        return {
            "status": state.status.value,
            "variables": state.variables,
            "node_history": state.node_history,
        }

    async def _execute_function(self, function: Callable, context: dict) -> Any:
        """执行函数"""
        if asyncio.iscoroutinefunction(function):
            return await function(context)
        else:
            return function(context)

    async def _execute_parallel(self, function: Callable, context: dict) -> dict:
        """并行执行"""
        # 简化实现：这里可以扩展为真正的并行执行
        return await self._execute_function(function, context)

    def _get_next_node(self, node: WorkflowNode, context: dict) -> str | None:
        """获取下一个节点"""
        if not node.next_nodes:
            return None

        # 如果是条件节点
        if "conditional_next" in node.metadata:
            conditional_next = node.metadata["conditional_next"]
            decision = context.get("_last_decision", False)

            # 根据决策选择下一个节点
            for condition_key, next_node_id in conditional_next.items():
                if condition_key == "else" and not decision or decision and condition_key != "else":
                    return next_node_id

        # 默认返回第一个下一个节点
        return node.next_nodes[0] if node.next_nodes else None

    def register_function(self, name: str, function: Callable):
        """注册函数到registry"""
        self.function_registry[name] = function
        logger.debug(f"Registered function: {name}")

    def get_workflow_status(self, workflow_id: str) -> dict | None:
        """获取工作流状态"""
        # 尝试从checkpoint加载
        import asyncio

        state = asyncio.run(self.checkpoint_manager.load_checkpoint(workflow_id))

        if state:
            return {
                "workflow_id": state.workflow_id,
                "status": state.status.value,
                "current_node": state.current_node,
                "node_history": state.node_history,
                "created_at": state.created_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
            }

        return None

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_executions"] / self.stats["total_executions"]
                if self.stats["total_executions"] > 0
                else 0.0
            ),
        }
