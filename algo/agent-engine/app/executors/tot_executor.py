"""
Tree of Thoughts (ToT) 执行器

多路径思考、探索与回溯。
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """节点状态"""

    UNEXPLORED = "unexplored"  # 未探索
    EXPLORING = "exploring"  # 探索中
    COMPLETE = "complete"  # 已完成
    FAILED = "failed"  # 失败
    PRUNED = "pruned"  # 被剪枝


@dataclass
class ThoughtNode:
    """思考节点"""

    node_id: str
    thought: str  # 思考内容
    parent_id: str | None
    children_ids: list[str] = field(default_factory=list)
    depth: int = 0
    score: float = 0.0  # 评分（0-1）
    status: NodeStatus = NodeStatus.UNEXPLORED
    result: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToTResult:
    """ToT 执行结果"""

    task: str
    best_path: list[ThoughtNode]
    all_nodes: list[ThoughtNode]
    final_answer: str
    exploration_stats: dict


class TreeOfThoughtsExecutor:
    """
    Tree of Thoughts 执行器

    用法:
        executor = TreeOfThoughtsExecutor(llm_client, tool_registry)

        result = await executor.execute(
            task="Solve the 24 game with numbers 4, 9, 10, 13",
            max_depth=4,
            branch_factor=3,
            beam_width=5
        )
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        model: str = "gpt-4",
        max_depth: int = 5,
        branch_factor: int = 3,
        beam_width: int = 5,
    ):
        """
        初始化 ToT 执行器

        Args:
            llm_client: LLM 客户端
            tool_registry: 工具注册表
            model: 使用的模型
            max_depth: 最大深度
            branch_factor: 每个节点的分支数
            beam_width: Beam Search 宽度
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.model = model
        self.max_depth = max_depth
        self.branch_factor = branch_factor
        self.beam_width = beam_width

        # 节点存储
        self.nodes: dict[str, ThoughtNode] = {}
        self.node_counter = 0

        logger.info(
            f"TreeOfThoughtsExecutor initialized (max_depth={max_depth}, "
            f"branch_factor={branch_factor}, beam_width={beam_width})"
        )

    async def execute(
        self,
        task: str,
        initial_context: dict | None = None,
    ) -> ToTResult:
        """
        执行 ToT

        Args:
            task: 任务描述
            initial_context: 初始上下文

        Returns:
            ToT 执行结果
        """
        logger.info(f"Starting Tree of Thoughts for task: {task[:50]}...")

        # 创建根节点
        root = self._create_node(
            thought=f"Task: {task}",
            parent_id=None,
            depth=0,
        )
        self.nodes[root.node_id] = root

        # Beam Search 探索
        current_beam = [root]

        for depth in range(1, self.max_depth + 1):
            logger.info(f"Exploring depth {depth}, beam size: {len(current_beam)}")

            # 为 beam 中的每个节点生成子节点
            all_candidates = []

            for node in current_beam:
                if node.status == NodeStatus.COMPLETE:
                    # 已完成的节点不再扩展
                    all_candidates.append(node)
                    continue

                # 生成子思考
                children = await self._generate_children(node, task, depth)

                # 评估子节点
                for child in children:
                    score = await self._evaluate_node(child, task)
                    child.score = score
                    self.nodes[child.node_id] = child
                    all_candidates.append(child)

                    # 检查是否达成目标
                    if await self._is_goal_reached(child, task):
                        child.status = NodeStatus.COMPLETE
                        logger.info(f"Goal reached at node {child.node_id}")

            # 选择 top-k（Beam Search）
            all_candidates.sort(key=lambda n: n.score, reverse=True)
            current_beam = all_candidates[: self.beam_width]

            # 如果有完成的节点，提前结束
            if any(n.status == NodeStatus.COMPLETE for n in current_beam):
                break

        # 选择最佳路径
        best_node = max(current_beam, key=lambda n: n.score)
        best_path = self._trace_path(best_node)

        # 生成最终答案
        final_answer = await self._synthesize_answer(best_path, task)

        # 统计信息
        stats = {
            "total_nodes": len(self.nodes),
            "max_depth_reached": max(n.depth for n in self.nodes.values()),
            "best_score": best_node.score,
            "completed_nodes": sum(
                1 for n in self.nodes.values() if n.status == NodeStatus.COMPLETE
            ),
        }

        logger.info(f"ToT completed: {stats['total_nodes']} nodes explored")

        return ToTResult(
            task=task,
            best_path=best_path,
            all_nodes=list(self.nodes.values()),
            final_answer=final_answer,
            exploration_stats=stats,
        )

    async def _generate_children(
        self, parent: ThoughtNode, task: str, depth: int
    ) -> list[ThoughtNode]:
        """生成子思考节点"""
        # 构建上下文
        path_so_far = self._trace_path(parent)
        context = "\n".join([f"Step {i + 1}: {n.thought}" for i, n in enumerate(path_so_far)])

        prompt = f"""任务: {task}

当前思考路径:
{context}

请生成 {self.branch_factor} 个可能的下一步思考方向。要求:
1. 每个思考要有创新性和差异性
2. 逻辑清晰，向目标推进
3. 避免重复

以 JSON 数组格式输出:
[
  {{"thought": "思考内容1"}},
  {{"thought": "思考内容2"}},
  {{"thought": "思考内容3"}}
]"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.7,
                response_format={"type": "json_object"},
            )

            thoughts = response.get("thoughts", [])[: self.branch_factor]

            children = []
            for t in thoughts:
                child = self._create_node(
                    thought=t["thought"],
                    parent_id=parent.node_id,
                    depth=depth,
                )
                parent.children_ids.append(child.node_id)
                children.append(child)

            return children

        except Exception as e:
            logger.error(f"Error generating children: {e}")
            return []

    async def _evaluate_node(self, node: ThoughtNode, task: str) -> float:
        """评估节点（打分）"""
        prompt = f"""任务: {task}

当前思考: {node.thought}

请评估这个思考的质量（0-1分）。评估标准:
- 是否接近解决任务
- 逻辑是否合理
- 是否有创新性

只输出一个 0-1 之间的数字，不要解释。"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.0,
            )

            score = float(response.strip())
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error evaluating node: {e}")
            return 0.5  # 默认中等分数

    async def _is_goal_reached(self, node: ThoughtNode, task: str) -> bool:
        """检查是否达成目标"""
        prompt = f"""任务: {task}

当前思考: {node.thought}

这个思考是否已经解决了任务？回答 true 或 false。"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.0,
            )

            return response.strip().lower() in ["true", "yes"]

        except Exception as e:
            logger.error(f"Error checking goal: {e}")
            return False

    async def _synthesize_answer(self, path: list[ThoughtNode], task: str) -> str:
        """综合路径生成最终答案"""
        path_text = "\n".join([f"Step {i + 1}: {n.thought}" for i, n in enumerate(path)])

        prompt = f"""任务: {task}

思考路径:
{path_text}

请根据以上思考路径，生成最终答案。要求简洁明了。"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.3,
        )

        return response.strip()

    def _create_node(self, thought: str, parent_id: str | None, depth: int) -> ThoughtNode:
        """创建节点"""
        node_id = f"node_{self.node_counter}"
        self.node_counter += 1

        return ThoughtNode(
            node_id=node_id,
            thought=thought,
            parent_id=parent_id,
            depth=depth,
        )

    def _trace_path(self, node: ThoughtNode) -> list[ThoughtNode]:
        """回溯路径"""
        path = []
        current = node

        while current:
            path.append(current)
            if current.parent_id:
                current = self.nodes.get(current.parent_id)
            else:
                break

        return list(reversed(path))

    def clear(self):
        """清空节点"""
        self.nodes = {}
        self.node_counter = 0
