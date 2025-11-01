"""
Graph Store - 知识图谱存储

支持 networkx（轻量级）和 Neo4j（企业级）两种后端
"""

import json
import logging
from typing import Any

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None

logger = logging.getLogger(__name__)


class GraphStore:
    """知识图谱存储（支持 networkx 和 Neo4j）"""

    def __init__(
        self,
        backend: str = "networkx",  # "networkx" or "neo4j"
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
    ):
        """
        初始化图谱存储

        Args:
            backend: 后端类型（networkx 或 neo4j）
            neo4j_uri: Neo4j URI（仅 neo4j 后端）
            neo4j_user: Neo4j 用户名
            neo4j_password: Neo4j 密码
        """
        self.backend = backend

        if backend == "networkx":
            if not NETWORKX_AVAILABLE:
                raise ImportError("networkx not installed. Install with: pip install networkx")
            self.graph = nx.DiGraph()
            logger.info("Graph store initialized with networkx backend")

        elif backend == "neo4j":
            if not NEO4J_AVAILABLE:
                raise ImportError("neo4j not installed. Install with: pip install neo4j")
            if not all([neo4j_uri, neo4j_user, neo4j_password]):
                raise ValueError("Neo4j credentials required")

            self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            logger.info(f"Graph store initialized with Neo4j backend: {neo4j_uri}")

        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any]):
        """
        添加节点

        Args:
            node_id: 节点 ID
            node_type: 节点类型（Entity/Document）
            properties: 节点属性
        """
        if self.backend == "networkx":
            self.graph.add_node(node_id, node_type=node_type, **properties)

        elif self.backend == "neo4j":
            with self.driver.session() as session:
                session.run(
                    f"""
                    MERGE (n:{node_type} {{id: $node_id}})
                    SET n += $properties
                    """,
                    node_id=node_id,
                    properties=properties,
                )

        logger.debug(f"Added node: {node_id} ({node_type})")

    def add_edge(
        self, source_id: str, target_id: str, relation: str, properties: dict | None = None
    ):
        """
        添加边

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            relation: 关系类型
            properties: 边属性
        """
        properties = properties or {}

        if self.backend == "networkx":
            self.graph.add_edge(source_id, target_id, relation=relation, **properties)

        elif self.backend == "neo4j":
            with self.driver.session() as session:
                session.run(
                    f"""
                    MATCH (a {{id: $source_id}})
                    MATCH (b {{id: $target_id}})
                    MERGE (a)-[r:{relation}]->(b)
                    SET r += $properties
                    """,
                    source_id=source_id,
                    target_id=target_id,
                    properties=properties,
                )

        logger.debug(f"Added edge: {source_id} -[{relation}]-> {target_id}")

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """获取节点信息"""
        if self.backend == "networkx":
            if node_id in self.graph:
                return dict(self.graph.nodes[node_id])
            return None

        elif self.backend == "neo4j":
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n {id: $node_id})
                    RETURN n
                    """,
                    node_id=node_id,
                )
                record = result.single()
                if record:
                    return dict(record["n"])
                return None

    def get_neighbors(
        self, node_id: str, relation: str | None = None, max_hops: int = 1
    ) -> list[dict[str, Any]]:
        """
        获取邻居节点

        Args:
            node_id: 节点 ID
            relation: 关系类型过滤（可选）
            max_hops: 最大跳数

        Returns:
            邻居节点列表
        """
        if self.backend == "networkx":
            return self._get_neighbors_nx(node_id, relation, max_hops)
        elif self.backend == "neo4j":
            return self._get_neighbors_neo4j(node_id, relation, max_hops)

    def _get_neighbors_nx(
        self, node_id: str, relation: str | None, max_hops: int
    ) -> list[dict[str, Any]]:
        """NetworkX 实现"""
        if node_id not in self.graph:
            return []

        neighbors = []
        visited = {node_id}
        current_level = {node_id}

        for hop in range(max_hops):
            next_level = set()
            for current_node in current_level:
                for neighbor in self.graph.successors(current_node):
                    if neighbor not in visited:
                        edge_data = self.graph[current_node][neighbor]
                        if relation is None or edge_data.get("relation") == relation:
                            node_data = dict(self.graph.nodes[neighbor])
                            node_data["id"] = neighbor
                            node_data["hop"] = hop + 1
                            node_data["relation"] = edge_data.get("relation")
                            neighbors.append(node_data)
                            visited.add(neighbor)
                            next_level.add(neighbor)

            current_level = next_level
            if not current_level:
                break

        return neighbors

    def _get_neighbors_neo4j(
        self, node_id: str, relation: str | None, max_hops: int
    ) -> list[dict[str, Any]]:
        """Neo4j 实现"""
        with self.driver.session() as session:
            relation_filter = f":{relation}" if relation else ""
            result = session.run(
                f"""
                MATCH path = (start {{id: $node_id}})-[{relation_filter}*1..{max_hops}]->(end)
                RETURN end, length(path) as hop
                ORDER BY hop
                """,
                node_id=node_id,
            )

            neighbors = []
            for record in result:
                node = dict(record["end"])
                node["hop"] = record["hop"]
                neighbors.append(node)

            return neighbors

    def find_path(
        self, source_id: str, target_id: str, max_hops: int = 3
    ) -> list[list[dict[str, Any]]]:
        """
        查找路径

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            max_hops: 最大跳数

        Returns:
            路径列表（每个路径是节点列表）
        """
        if self.backend == "networkx":
            return self._find_path_nx(source_id, target_id, max_hops)
        elif self.backend == "neo4j":
            return self._find_path_neo4j(source_id, target_id, max_hops)

    def _find_path_nx(
        self, source_id: str, target_id: str, max_hops: int
    ) -> list[list[dict[str, Any]]]:
        """NetworkX 路径查找"""
        if source_id not in self.graph or target_id not in self.graph:
            return []

        try:
            paths = []
            for path in nx.all_simple_paths(self.graph, source_id, target_id, cutoff=max_hops):
                path_nodes = []
                for i, node_id in enumerate(path):
                    node_data = dict(self.graph.nodes[node_id])
                    node_data["id"] = node_id
                    node_data["position"] = i

                    # 添加边信息
                    if i < len(path) - 1:
                        edge_data = self.graph[node_id][path[i + 1]]
                        node_data["relation_to_next"] = edge_data.get("relation")

                    path_nodes.append(node_data)
                paths.append(path_nodes)

            return paths[:10]  # 限制返回路径数
        except nx.NetworkXNoPath:
            return []

    def _find_path_neo4j(
        self, source_id: str, target_id: str, max_hops: int
    ) -> list[list[dict[str, Any]]]:
        """Neo4j 路径查找"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (start {id: $source_id})-[*1..$max_hops]->(end {id: $target_id})
                RETURN nodes(path) as path_nodes, relationships(path) as path_rels
                LIMIT 10
                """,
                source_id=source_id,
                target_id=target_id,
                max_hops=max_hops,
            )

            paths = []
            for record in result:
                path_nodes = []
                nodes = record["path_nodes"]
                rels = record["path_rels"]

                for i, node in enumerate(nodes):
                    node_data = dict(node)
                    node_data["position"] = i
                    if i < len(rels):
                        node_data["relation_to_next"] = rels[i].type
                    path_nodes.append(node_data)

                paths.append(path_nodes)

            return paths

    def get_stats(self) -> dict[str, Any]:
        """获取图谱统计信息"""
        if self.backend == "networkx":
            return {
                "backend": "networkx",
                "num_nodes": self.graph.number_of_nodes(),
                "num_edges": self.graph.number_of_edges(),
                "is_connected": nx.is_weakly_connected(self.graph),
            }

        elif self.backend == "neo4j":
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    RETURN count(n) as num_nodes
                    """
                )
                num_nodes = result.single()["num_nodes"]

                result = session.run(
                    """
                    MATCH ()-[r]->()
                    RETURN count(r) as num_edges
                    """
                )
                num_edges = result.single()["num_edges"]

                return {
                    "backend": "neo4j",
                    "num_nodes": num_nodes,
                    "num_edges": num_edges,
                }

    def save_to_file(self, filepath: str):
        """保存图谱到文件（仅 networkx）"""
        if self.backend != "networkx":
            raise NotImplementedError("Save to file only supported for networkx backend")

        data = nx.node_link_data(self.graph)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Graph saved to {filepath}")

    def load_from_file(self, filepath: str):
        """从文件加载图谱（仅 networkx）"""
        if self.backend != "networkx":
            raise NotImplementedError("Load from file only supported for networkx backend")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data)
        logger.info(f"Graph loaded from {filepath}")

    def close(self):
        """关闭连接"""
        if self.backend == "neo4j" and hasattr(self, "driver"):
            self.driver.close()
            logger.info("Neo4j connection closed")


# 全局实例
_graph_store: GraphStore | None = None


def get_graph_store(
    backend: str = "networkx",
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
) -> GraphStore:
    """
    获取图谱存储实例（单例）

    Args:
        backend: 后端类型
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j 用户名
        neo4j_password: Neo4j 密码

    Returns:
        GraphStore 实例
    """
    global _graph_store

    if _graph_store is None:
        _graph_store = GraphStore(
            backend=backend,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
        )

    return _graph_store
