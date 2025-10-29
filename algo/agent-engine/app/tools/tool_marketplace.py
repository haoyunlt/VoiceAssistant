"""Agent工具市场"""
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class Tool:
    """工具定义"""

    def __init__(
        self,
        tool_id: str,
        name: str,
        description: str,
        category: str,
        version: str,
        execute_func: Callable,
        parameters_schema: dict[str, Any],
        author: str = "system",
        tags: list[str] | None = None
    ):
        self.tool_id = tool_id
        self.name = name
        self.description = description
        self.category = category
        self.version = version
        self.execute_func = execute_func
        self.parameters_schema = parameters_schema
        self.author = author
        self.tags = tags or []
        self.created_at = datetime.now()
        self.usage_count = 0
        self.rating = 0.0
        self.enabled = True


class ToolMarketplace:
    """
    Agent工具市场

    功能：
    1. 工具注册：开发者可以注册自定义工具
    2. 工具发现：基于需求搜索合适的工具
    3. 工具评分：用户可以对工具进行评分
    4. 工具版本管理：支持工具的版本更新
    5. 工具组合：将多个工具组合成工作流
    """

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.categories: dict[str, list[str]] = {}
        self.tool_usage_log: list[dict] = []

    def register_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        category: str,
        version: str,
        execute_func: Callable,
        parameters_schema: dict[str, Any],
        author: str = "system",
        tags: list[str] | None = None
    ) -> bool:
        """
        注册工具

        Args:
            tool_id: 工具唯一标识
            name: 工具名称
            description: 工具描述
            category: 工具分类
            version: 版本号
            execute_func: 执行函数
            parameters_schema: 参数模式（JSON Schema）
            author: 作者
            tags: 标签

        Returns:
            是否注册成功
        """
        if tool_id in self.tools:
            logger.warning(f"Tool {tool_id} already exists")
            return False

        tool = Tool(
            tool_id=tool_id,
            name=name,
            description=description,
            category=category,
            version=version,
            execute_func=execute_func,
            parameters_schema=parameters_schema,
            author=author,
            tags=tags
        )

        self.tools[tool_id] = tool

        # 添加到分类
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(tool_id)

        logger.info(f"Registered tool: {name} ({tool_id})")
        return True

    def unregister_tool(self, tool_id: str) -> bool:
        """注销工具"""
        if tool_id not in self.tools:
            return False

        tool = self.tools[tool_id]

        # 从分类中移除
        if tool.category in self.categories:
            self.categories[tool.category].remove(tool_id)

        del self.tools[tool_id]

        logger.info(f"Unregistered tool: {tool_id}")
        return True

    def get_tool(self, tool_id: str) -> Tool | None:
        """获取工具"""
        return self.tools.get(tool_id)

    def list_tools(
        self,
        category: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
        enabled_only: bool = True
    ) -> list[Tool]:
        """
        列出工具

        Args:
            category: 按分类过滤
            tags: 按标签过滤
            author: 按作者过滤
            enabled_only: 只显示启用的工具

        Returns:
            工具列表
        """
        tools = list(self.tools.values())

        # 过滤
        if category:
            tools = [t for t in tools if t.category == category]

        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]

        if author:
            tools = [t for t in tools if t.author == author]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        # 按评分和使用次数排序
        tools.sort(key=lambda t: (t.rating, t.usage_count), reverse=True)

        return tools

    def search_tools(
        self,
        query: str,
        top_k: int = 5
    ) -> list[Tool]:
        """
        搜索工具

        Args:
            query: 搜索查询
            top_k: 返回前k个结果

        Returns:
            匹配的工具列表
        """
        query_lower = query.lower()

        scored_tools = []

        for tool in self.tools.values():
            if not tool.enabled:
                continue

            score = 0.0

            # 名称匹配
            if query_lower in tool.name.lower():
                score += 10.0

            # 描述匹配
            if query_lower in tool.description.lower():
                score += 5.0

            # 标签匹配
            for tag in tool.tags:
                if query_lower in tag.lower():
                    score += 3.0

            # 考虑评分和使用次数
            score += tool.rating * 0.5
            score += min(tool.usage_count / 100, 2.0)

            if score > 0:
                scored_tools.append((score, tool))

        # 排序
        scored_tools.sort(key=lambda x: x[0], reverse=True)

        return [tool for _, tool in scored_tools[:top_k]]

    async def execute_tool(
        self,
        tool_id: str,
        parameters: dict[str, Any],
        user_id: str | None = None
    ) -> dict[str, Any]:
        """
        执行工具

        Args:
            tool_id: 工具ID
            parameters: 执行参数
            user_id: 用户ID

        Returns:
            执行结果
        """
        tool = self.get_tool(tool_id)

        if not tool:
            return {
                "success": False,
                "error": f"Tool not found: {tool_id}"
            }

        if not tool.enabled:
            return {
                "success": False,
                "error": f"Tool is disabled: {tool_id}"
            }

        # 验证参数
        validation_result = self._validate_parameters(
            parameters,
            tool.parameters_schema
        )

        if not validation_result["valid"]:
            return {
                "success": False,
                "error": f"Invalid parameters: {validation_result['error']}"
            }

        # 执行工具
        try:
            import asyncio

            if asyncio.iscoroutinefunction(tool.execute_func):
                result = await tool.execute_func(**parameters)
            else:
                result = tool.execute_func(**parameters)

            # 更新统计
            tool.usage_count += 1

            # 记录使用
            self._log_tool_usage(tool_id, user_id, parameters, result)

            return {
                "success": True,
                "result": result,
                "tool_id": tool_id,
                "tool_name": tool.name
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_id": tool_id
            }

    def rate_tool(
        self,
        tool_id: str,
        rating: float,
        user_id: str | None = None
    ) -> bool:
        """
        为工具评分

        Args:
            tool_id: 工具ID
            rating: 评分（0-5）
            user_id: 用户ID

        Returns:
            是否成功
        """
        tool = self.get_tool(tool_id)

        if not tool:
            return False

        if rating < 0 or rating > 5:
            return False

        # 更新评分（简单平均）
        old_rating = tool.rating
        old_count = tool.usage_count

        tool.rating = (old_rating * old_count + rating) / (old_count + 1)

        logger.info(f"Tool {tool_id} rated: {rating} (new avg: {tool.rating:.2f})")

        return True

    def get_tool_stats(self, tool_id: str) -> dict[str, Any] | None:
        """获取工具统计信息"""
        tool = self.get_tool(tool_id)

        if not tool:
            return None

        # 从日志中统计
        usage_logs = [
            log for log in self.tool_usage_log
            if log["tool_id"] == tool_id
        ]

        success_count = sum(1 for log in usage_logs if log.get("success", False))
        failure_count = len(usage_logs) - success_count

        return {
            "tool_id": tool_id,
            "name": tool.name,
            "usage_count": tool.usage_count,
            "rating": tool.rating,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(usage_logs) if usage_logs else 0,
            "created_at": tool.created_at.isoformat()
        }

    def recommend_tools(
        self,
        task_description: str,
        user_history: list[str] | None = None,
        top_k: int = 5
    ) -> list[Tool]:
        """
        推荐工具

        Args:
            task_description: 任务描述
            user_history: 用户历史使用的工具ID列表
            top_k: 返回数量

        Returns:
            推荐的工具列表
        """
        # 基于任务描述搜索
        relevant_tools = self.search_tools(task_description, top_k * 2)

        # 如果有用户历史，提升相关工具的排名
        if user_history:
            for tool in relevant_tools:
                if tool.tool_id in user_history:
                    # 给使用过的工具加分
                    tool._recommendation_score = getattr(tool, '_recommendation_score', 0) + 2.0

        # 重新排序
        relevant_tools.sort(
            key=lambda t: getattr(t, '_recommendation_score', 0) + t.rating + (t.usage_count / 100),
            reverse=True
        )

        return relevant_tools[:top_k]

    def create_tool_workflow(
        self,
        workflow_name: str,
        tool_sequence: list[dict[str, Any]]
    ) -> str:
        """
        创建工具工作流

        Args:
            workflow_name: 工作流名称
            tool_sequence: 工具序列，每个元素包含 tool_id 和 parameter_mapping

        Returns:
            工作流ID
        """
        import uuid

        workflow_id = str(uuid.uuid4())

        workflow = {
            "workflow_id": workflow_id,
            "name": workflow_name,
            "sequence": tool_sequence,
            "created_at": datetime.now().isoformat()
        }

        # 保存工作流（这里简化，实际应持久化）
        if not hasattr(self, 'workflows'):
            self.workflows = {}

        self.workflows[workflow_id] = workflow

        logger.info(f"Created workflow: {workflow_name} ({workflow_id})")

        return workflow_id

    async def execute_workflow(
        self,
        workflow_id: str,
        initial_parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流ID
            initial_parameters: 初始参数

        Returns:
            执行结果
        """
        if not hasattr(self, 'workflows'):
            return {"success": False, "error": "No workflows defined"}

        workflow = self.workflows.get(workflow_id)

        if not workflow:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        results = []
        current_output = initial_parameters

        for step in workflow["sequence"]:
            tool_id = step["tool_id"]
            parameter_mapping = step.get("parameter_mapping", {})

            # 映射参数
            tool_params = {}
            for param_name, source in parameter_mapping.items():
                if source.startswith("$"):
                    # 从上一步结果中获取
                    key = source[1:]
                    tool_params[param_name] = current_output.get(key)
                else:
                    tool_params[param_name] = source

            # 执行工具
            result = await self.execute_tool(tool_id, tool_params)

            results.append({
                "tool_id": tool_id,
                "result": result
            })

            if not result.get("success"):
                # 工作流失败
                return {
                    "success": False,
                    "error": f"Workflow failed at step {len(results)}",
                    "results": results
                }

            # 更新当前输出
            current_output = result.get("result", {})

        return {
            "success": True,
            "results": results,
            "final_output": current_output
        }

    def _validate_parameters(
        self,
        parameters: dict[str, Any],
        schema: dict[str, Any]
    ) -> dict[str, Any]:
        """验证参数"""
        # 简化实现：检查必需参数
        required = schema.get("required", [])

        for param in required:
            if param not in parameters:
                return {
                    "valid": False,
                    "error": f"Missing required parameter: {param}"
                }

        return {"valid": True}

    def _log_tool_usage(
        self,
        tool_id: str,
        user_id: str | None,
        parameters: dict[str, Any],
        result: Any
    ):
        """记录工具使用"""
        log_entry = {
            "tool_id": tool_id,
            "user_id": user_id,
            "parameters": parameters,
            "success": result is not None,
            "timestamp": datetime.now().isoformat()
        }

        self.tool_usage_log.append(log_entry)

        # 保持日志在合理大小
        if len(self.tool_usage_log) > 10000:
            self.tool_usage_log = self.tool_usage_log[-5000:]

    def export_marketplace_stats(self) -> dict[str, Any]:
        """导出市场统计信息"""
        return {
            "total_tools": len(self.tools),
            "categories": {
                cat: len(tool_ids)
                for cat, tool_ids in self.categories.items()
            },
            "total_usage": sum(t.usage_count for t in self.tools.values()),
            "top_tools": [
                {
                    "tool_id": t.tool_id,
                    "name": t.name,
                    "usage_count": t.usage_count,
                    "rating": t.rating
                }
                for t in sorted(
                    self.tools.values(),
                    key=lambda x: x.usage_count,
                    reverse=True
                )[:10]
            ]
        }
