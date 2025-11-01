"""
Graph Retriever - 图谱检索器

在知识图谱中执行检索和路径查询
"""

import logging
from typing import Any

from app.graph.graph_store import GraphStore

logger = logging.getLogger(__name__)


class GraphRetriever:
    """图谱检索器"""

    def __init__(self, graph_store: GraphStore):
        """
        初始化图谱检索器

        Args:
            graph_store: 图谱存储实例
        """
        self.graph_store = graph_store
        logger.info("Graph retriever initialized")

    async def query(
        self,
        _query: str,
        entities: list[str],
        max_hops: int = 2,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        执行图谱查询

        Args:
            query: 原始查询
            entities: 查询中的实体列表
            max_hops: 最大跳数
            top_k: 返回结果数

        Returns:
            图谱检索结果
        """
        results = []

        for entity in entities:
            # 查找实体节点
            entity_node = self.graph_store.get_node(entity)

            if entity_node:
                # 获取邻居节点
                neighbors = self.graph_store.get_neighbors(entity, max_hops=max_hops)

                for neighbor in neighbors:
                    results.append(
                        {
                            "type": "graph_node",
                            "entity": entity,
                            "neighbor": neighbor,
                            "hop": neighbor.get("hop", 1),
                            "relation": neighbor.get("relation"),
                            "content": self._format_node_content(neighbor),
                            "score": 1.0 / (neighbor.get("hop", 1) + 1),  # 距离越近分数越高
                        }
                    )

        # 按分数排序
        results = sorted(results, key=lambda x: x["score"], reverse=True)

        logger.info(f"Graph query returned {len(results)} results for entities: {entities}")
        return results[:top_k]

    async def find_multi_hop_paths(
        self,
        start_entities: list[str],
        end_entities: list[str],
        max_hops: int = 3,
    ) -> list[dict[str, Any]]:
        """
        查找多跳路径

        Args:
            start_entities: 起始实体列表
            end_entities: 目标实体列表
            max_hops: 最大跳数

        Returns:
            路径列表
        """
        paths = []

        for start_entity in start_entities:
            for end_entity in end_entities:
                # 查找路径
                found_paths = self.graph_store.find_path(start_entity, end_entity, max_hops)

                for path_nodes in found_paths:
                    path_text = self._format_path(path_nodes)
                    paths.append(
                        {
                            "type": "graph_path",
                            "start": start_entity,
                            "end": end_entity,
                            "length": len(path_nodes),
                            "path": path_nodes,
                            "content": path_text,
                            "score": 1.0 / len(path_nodes),  # 路径越短分数越高
                        }
                    )

        # 按分数排序
        paths = sorted(paths, key=lambda x: x["score"], reverse=True)

        logger.info(f"Found {len(paths)} multi-hop paths")
        return paths

    def _format_node_content(self, node: dict[str, Any]) -> str:
        """格式化节点内容"""
        node_id = node.get("id", "")
        node_type = node.get("node_type", "Unknown")
        name = node.get("name", node_id)
        description = node.get("description", "")

        content = f"[{node_type}] {name}"
        if description:
            content += f": {description}"

        return content

    def _format_path(self, path_nodes: list[dict[str, Any]]) -> str:
        """格式化路径为文本"""
        path_parts = []

        for node in path_nodes:
            name = node.get("name", node.get("id", ""))
            path_parts.append(name)

            # 添加关系
            if "relation_to_next" in node:
                path_parts.append(f"-[{node['relation_to_next']}]->")

        return " ".join(path_parts)

    async def get_subgraph(
        self,
        entity: str,
        max_hops: int = 2,
    ) -> dict[str, Any]:
        """
        获取实体的子图

        Args:
            entity: 实体名称
            max_hops: 最大跳数

        Returns:
            子图信息（节点和边）
        """
        nodes = []
        edges = []

        # 获取中心节点
        center_node = self.graph_store.get_node(entity)
        if not center_node:
            return {"nodes": [], "edges": []}

        nodes.append({"id": entity, **center_node})

        # 获取邻居
        neighbors = self.graph_store.get_neighbors(entity, max_hops=max_hops)

        for neighbor in neighbors:
            neighbor_id = neighbor.get("id", "")
            nodes.append(neighbor)

            # 添加边（简化）
            edges.append(
                {
                    "source": entity,
                    "target": neighbor_id,
                    "relation": neighbor.get("relation", "related_to"),
                }
            )

        return {"nodes": nodes, "edges": edges, "center": entity}
