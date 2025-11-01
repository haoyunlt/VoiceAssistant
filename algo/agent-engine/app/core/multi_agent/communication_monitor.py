"""
Agent Communication Monitor - Agent间通信监控

实现功能：
- 消息追踪
- 通信统计
- 异常检测
- 性能监控
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


# Prometheus指标
agent_messages_total = Counter(
    "agent_messages_total",
    "Total messages between agents",
    ["from_agent", "to_agent", "message_type"],
)

agent_message_size_bytes = Histogram(
    "agent_message_size_bytes", "Message size in bytes", ["from_agent", "to_agent"]
)

agent_message_latency_seconds = Histogram(
    "agent_message_latency_seconds", "Message processing latency", ["from_agent", "to_agent"]
)


@dataclass
class MessageRecord:
    """消息记录"""

    message_id: str
    from_agent: str
    to_agent: str
    message_type: str
    content_preview: str  # 内容预览（前100字符）
    size_bytes: int
    timestamp: datetime
    latency: float | None = None  # 处理延迟（秒）
    status: str = "sent"  # sent, received, processed, failed
    metadata: dict = field(default_factory=dict)


class CommunicationMonitor:
    """
    Agent间通信监控器

    用法:
        monitor = CommunicationMonitor()

        # 记录消息发送
        message_id = monitor.record_message_sent(
            from_agent="researcher_01",
            to_agent="planner_01",
            message_type="request",
            content="请制定调研计划",
            metadata={"task_id": "task_123"}
        )

        # 记录消息接收
        monitor.record_message_received(message_id)

        # 记录消息处理完成
        monitor.record_message_processed(message_id, latency=0.5)

        # 获取统计信息
        stats = monitor.get_stats()
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history

        # 消息历史
        self.message_history: dict[str, MessageRecord] = {}
        self.history_queue: list[str] = []  # FIFO队列

        # 统计信息
        self.stats = {
            "total_messages": 0,
            "messages_by_type": defaultdict(int),
            "messages_by_agent_pair": defaultdict(int),
            "avg_latency": 0.0,
            "total_latency": 0.0,
            "processed_messages": 0,
            "failed_messages": 0,
        }

        logger.info("CommunicationMonitor initialized")

    def record_message_sent(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """
        记录消息发送

        Returns:
            message_id: 消息ID
        """
        message_id = f"msg_{from_agent}_{to_agent}_{datetime.now().timestamp()}"

        # 计算消息大小
        content_bytes = content.encode("utf-8")
        size_bytes = len(content_bytes)

        # 创建记录
        record = MessageRecord(
            message_id=message_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content_preview=content[:100] + ("..." if len(content) > 100 else ""),
            size_bytes=size_bytes,
            timestamp=datetime.now(),
            status="sent",
            metadata=metadata or {},
        )

        # 保存记录
        self._add_to_history(message_id, record)

        # 更新统计
        self.stats["total_messages"] += 1
        self.stats["messages_by_type"][message_type] += 1
        pair_key = f"{from_agent}→{to_agent}"
        self.stats["messages_by_agent_pair"][pair_key] += 1

        # 更新Prometheus指标
        agent_messages_total.labels(
            from_agent=from_agent, to_agent=to_agent, message_type=message_type
        ).inc()

        agent_message_size_bytes.labels(from_agent=from_agent, to_agent=to_agent).observe(
            size_bytes
        )

        logger.debug(
            f"Message sent: {message_id} ({from_agent} → {to_agent}, "
            f"type={message_type}, size={size_bytes}B)"
        )

        return message_id

    def record_message_received(self, message_id: str):
        """记录消息接收"""
        if message_id in self.message_history:
            self.message_history[message_id].status = "received"
            logger.debug(f"Message received: {message_id}")

    def record_message_processed(self, message_id: str, latency: float):
        """
        记录消息处理完成

        Args:
            message_id: 消息ID
            latency: 处理延迟（秒）
        """
        if message_id in self.message_history:
            record = self.message_history[message_id]
            record.status = "processed"
            record.latency = latency

            # 更新统计
            self.stats["processed_messages"] += 1
            self.stats["total_latency"] += latency
            self.stats["avg_latency"] = (
                self.stats["total_latency"] / self.stats["processed_messages"]
            )

            # 更新Prometheus指标
            agent_message_latency_seconds.labels(
                from_agent=record.from_agent, to_agent=record.to_agent
            ).observe(latency)

            logger.debug(f"Message processed: {message_id} (latency={latency:.3f}s)")

    def record_message_failed(self, message_id: str, error: str):
        """记录消息处理失败"""
        if message_id in self.message_history:
            record = self.message_history[message_id]
            record.status = "failed"
            record.metadata["error"] = error

            self.stats["failed_messages"] += 1

            logger.warning(f"Message failed: {message_id}, error: {error}")

    def _add_to_history(self, message_id: str, record: MessageRecord):
        """添加到历史记录（FIFO队列）"""
        self.message_history[message_id] = record
        self.history_queue.append(message_id)

        # 限制历史记录数量
        if len(self.history_queue) > self.max_history:
            oldest_id = self.history_queue.pop(0)
            if oldest_id in self.message_history:
                del self.message_history[oldest_id]

    def get_message_history(
        self,
        from_agent: str | None = None,
        to_agent: str | None = None,
        message_type: str | None = None,
        limit: int = 100,
    ) -> list[MessageRecord]:
        """
        获取消息历史

        Args:
            from_agent: 发送方筛选
            to_agent: 接收方筛选
            message_type: 类型筛选
            limit: 返回数量限制

        Returns:
            消息记录列表（倒序，最新的在前）
        """
        records = []

        # 倒序遍历
        for message_id in reversed(self.history_queue):
            if len(records) >= limit:
                break

            record = self.message_history.get(message_id)
            if not record:
                continue

            # 筛选条件
            if from_agent and record.from_agent != from_agent:
                continue
            if to_agent and record.to_agent != to_agent:
                continue
            if message_type and record.message_type != message_type:
                continue

            records.append(record)

        return records

    def get_agent_communication_matrix(self) -> dict[str, dict[str, int]]:
        """
        获取Agent通信矩阵

        Returns:
            {from_agent: {to_agent: message_count}}
        """
        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for record in self.message_history.values():
            matrix[record.from_agent][record.to_agent] += 1

        return dict(matrix)

    def detect_communication_anomalies(self) -> list[dict]:
        """
        检测通信异常

        Returns:
            异常列表，每个异常包含type和description
        """
        anomalies = []

        # 1. 检测失败率过高
        if self.stats["total_messages"] > 10:
            failure_rate = self.stats["failed_messages"] / self.stats["total_messages"]
            if failure_rate > 0.1:  # 失败率超过10%
                anomalies.append(
                    {
                        "type": "high_failure_rate",
                        "description": f"消息失败率过高: {failure_rate:.1%}",
                        "severity": "warning",
                    }
                )

        # 2. 检测延迟异常
        if self.stats["avg_latency"] > 5.0:  # 平均延迟超过5秒
            anomalies.append(
                {
                    "type": "high_latency",
                    "description": f"平均消息延迟过高: {self.stats['avg_latency']:.2f}s",
                    "severity": "warning",
                }
            )

        # 3. 检测消息堆积
        pending_messages = sum(
            1 for record in self.message_history.values() if record.status in ["sent", "received"]
        )
        if pending_messages > 50:
            anomalies.append(
                {
                    "type": "message_backlog",
                    "description": f"消息堆积: {pending_messages} 条待处理",
                    "severity": "critical",
                }
            )

        # 4. 检测孤立Agent（没有通信）
        all_agents = set()
        communicating_agents = set()
        for record in self.message_history.values():
            all_agents.add(record.from_agent)
            all_agents.add(record.to_agent)
            communicating_agents.add(record.from_agent)
            communicating_agents.add(record.to_agent)

        isolated_agents = all_agents - communicating_agents
        if isolated_agents:
            anomalies.append(
                {
                    "type": "isolated_agents",
                    "description": f"孤立Agent: {', '.join(isolated_agents)}",
                    "severity": "info",
                }
            )

        return anomalies

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "messages_by_type": dict(self.stats["messages_by_type"]),
            "messages_by_agent_pair": dict(self.stats["messages_by_agent_pair"]),
            "failure_rate": (
                self.stats["failed_messages"] / self.stats["total_messages"]
                if self.stats["total_messages"] > 0
                else 0.0
            ),
            "processing_rate": (
                self.stats["processed_messages"] / self.stats["total_messages"]
                if self.stats["total_messages"] > 0
                else 0.0
            ),
        }

    def export_to_visualization(self) -> dict:
        """
        导出为可视化数据格式（用于前端展示）

        Returns:
            {
                "nodes": [...],  # Agent节点
                "links": [...],  # 通信连接
                "stats": {...}
            }
        """
        # 1. 收集所有Agent
        agents = set()
        for record in self.message_history.values():
            agents.add(record.from_agent)
            agents.add(record.to_agent)

        # 2. 创建节点
        nodes = [{"id": agent, "name": agent} for agent in agents]

        # 3. 创建连接
        links = []
        pair_counts = defaultdict(int)
        for record in self.message_history.values():
            pair = (record.from_agent, record.to_agent)
            pair_counts[pair] += 1

        for (from_agent, to_agent), count in pair_counts.items():
            links.append({"source": from_agent, "target": to_agent, "value": count})

        return {"nodes": nodes, "links": links, "stats": self.get_stats()}


# 全局单例
_communication_monitor: CommunicationMonitor | None = None


def get_communication_monitor() -> CommunicationMonitor:
    """获取全局通信监控器"""
    global _communication_monitor
    if _communication_monitor is None:
        _communication_monitor = CommunicationMonitor()
    return _communication_monitor
