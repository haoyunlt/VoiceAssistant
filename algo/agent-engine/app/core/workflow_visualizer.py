"""
Workflow Visualizer - 工作流可视化器

实现功能：
- 导出为Mermaid图
- 导出为JSON（用于前端渲染）
- 执行追踪可视化
"""

import logging

logger = logging.getLogger(__name__)


class WorkflowVisualizer:
    """
    工作流可视化器

    用法:
        visualizer = WorkflowVisualizer()

        # 导出为Mermaid图
        mermaid_code = visualizer.export_to_mermaid(workflow_config)

        # 导出为前端可渲染的JSON
        graph_data = visualizer.export_to_json(workflow_config)
    """

    def export_to_mermaid(self, workflow_config: dict) -> str:
        """
        导出为Mermaid流程图

        Args:
            workflow_config: 工作流配置
                {
                    "nodes": [...],
                    "edges": [...],
                    "entry": "start"
                }

        Returns:
            Mermaid代码字符串
        """
        lines = ["graph TD"]

        # 添加节点
        for node in workflow_config["nodes"]:
            node_id = node["id"]
            node_type = node["type"]
            label = node.get("label", node_id)

            # 根据节点类型选择形状
            if node_type == "action":
                shape = f"[{label}]"  # 方框
            elif node_type == "decision":
                shape = f"{{{label}}}"  # 菱形
            elif node_type == "parallel":
                shape = f'[["{label}"]]'  # 双边框
            else:
                shape = f"({label})"  # 圆角矩形

            lines.append(f"    {node_id}{shape}")

        # 添加边
        for edge in workflow_config["edges"]:
            from_node = edge["from"]
            to_node = edge["to"]

            if isinstance(to_node, dict):
                # 条件边
                for condition, target in to_node.items():
                    label = condition if condition != "else" else "否"
                    lines.append(f"    {from_node} -->|{label}| {target}")
            else:
                # 普通边
                lines.append(f"    {from_node} --> {to_node}")

        # 标记入口节点
        entry = workflow_config.get("entry")
        if entry:
            lines.insert(1, f"    Start([开始]) --> {entry}")

        mermaid_code = "\n".join(lines)

        logger.debug(f"Generated Mermaid code ({len(lines)} lines)")

        return mermaid_code

    def export_to_json(self, workflow_config: dict) -> dict:
        """
        导出为JSON（用于前端可视化）

        Returns:
            {
                "nodes": [{"id": "...", "label": "...", "type": "..."}],
                "edges": [{"source": "...", "target": "...", "label": "..."}]
            }
        """
        nodes = []
        edges = []

        # 转换节点
        for node in workflow_config["nodes"]:
            nodes.append(
                {
                    "id": node["id"],
                    "label": node.get("label", node["id"]),
                    "type": node["type"],
                    "metadata": node.get("metadata", {}),
                }
            )

        # 转换边
        for edge in workflow_config["edges"]:
            from_node = edge["from"]
            to_node = edge["to"]

            if isinstance(to_node, dict):
                # 条件边
                for condition, target in to_node.items():
                    edges.append(
                        {
                            "source": from_node,
                            "target": target,
                            "label": condition,
                            "type": "conditional",
                        }
                    )
            else:
                # 普通边
                edges.append(
                    {"source": from_node, "target": to_node, "label": "", "type": "normal"}
                )

        return {"nodes": nodes, "edges": edges, "entry": workflow_config.get("entry")}

    def visualize_execution_trace(
        self, workflow_config: dict, node_history: list[str], current_node: str | None = None
    ) -> str:
        """
        可视化执行追踪（Mermaid）

        Args:
            workflow_config: 工作流配置
            node_history: 已执行的节点历史
            current_node: 当前节点

        Returns:
            Mermaid代码（高亮执行路径）
        """
        lines = ["graph TD"]

        # 添加节点（已执行的用不同样式）
        for node in workflow_config["nodes"]:
            node_id = node["id"]
            label = node.get("label", node_id)

            # 根据执行状态选择样式
            if node_id == current_node:
                # 当前节点（黄色）
                lines.append(f"    {node_id}[{label}]")
                lines.append(f"    style {node_id} fill:#ffff00,stroke:#333,stroke-width:4px")
            elif node_id in node_history:
                # 已执行节点（绿色）
                lines.append(f"    {node_id}[{label}]")
                lines.append(f"    style {node_id} fill:#90ee90,stroke:#333,stroke-width:2px")
            else:
                # 未执行节点（灰色）
                lines.append(f"    {node_id}[{label}]")
                lines.append(f"    style {node_id} fill:#ddd,stroke:#333")

        # 添加边（已执行的用粗线）
        for edge in workflow_config["edges"]:
            from_node = edge["from"]
            to_node = edge["to"]

            if isinstance(to_node, dict):
                # 条件边
                for condition, target in to_node.items():
                    # 检查是否在执行路径中
                    if from_node in node_history and target in node_history:
                        lines.append(f"    {from_node} ==>|{condition}| {target}")
                    else:
                        lines.append(f"    {from_node} -.->|{condition}| {target}")
            else:
                # 普通边
                if from_node in node_history and to_node in node_history:
                    lines.append(f"    {from_node} ==> {to_node}")
                else:
                    lines.append(f"    {from_node} --> {to_node}")

        return "\n".join(lines)

    def export_execution_timeline(
        self, node_history: list[str], timestamps: list[str] | None = None
    ) -> dict:
        """
        导出执行时间线（用于前端展示）

        Args:
            node_history: 节点历史
            timestamps: 时间戳列表（可选）

        Returns:
            时间线数据
        """
        timeline = []

        for i, node_id in enumerate(node_history):
            entry = {
                "step": i + 1,
                "node": node_id,
                "timestamp": timestamps[i] if timestamps and i < len(timestamps) else None,
            }
            timeline.append(entry)

        return {"timeline": timeline, "total_steps": len(node_history)}


# 便捷函数
def visualize_workflow(workflow_config: dict) -> str:
    """
    快速可视化工作流

    Args:
        workflow_config: 工作流配置

    Returns:
        Mermaid代码
    """
    visualizer = WorkflowVisualizer()
    return visualizer.export_to_mermaid(workflow_config)


def visualize_execution(
    workflow_config: dict, node_history: list[str], current_node: str | None = None
) -> str:
    """
    快速可视化执行追踪

    Args:
        workflow_config: 工作流配置
        node_history: 节点历史
        current_node: 当前节点

    Returns:
        Mermaid代码
    """
    visualizer = WorkflowVisualizer()
    return visualizer.visualize_execution_trace(workflow_config, node_history, current_node)
