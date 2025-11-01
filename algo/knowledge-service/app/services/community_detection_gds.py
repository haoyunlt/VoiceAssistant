"""
Community Detection with Neo4j GDS - 使用Neo4j Graph Data Science进行社区检测

集成Louvain算法，提升社区检测质量
"""

import logging
from typing import Any
from datetime import datetime

from app.common.exceptions import CommunityDetectionError
from app.core.metrics import (
    community_detection_total,
    community_detection_duration,
    community_modularity,
)

logger = logging.getLogger(__name__)


class CommunityDetectionGDS:
    """基于Neo4j GDS的社区检测服务"""

    def __init__(self, neo4j_client):
        """
        初始化社区检测服务

        Args:
            neo4j_client: Neo4j客户端
        """
        self.neo4j = neo4j_client
        self._check_gds_available()

    def _check_gds_available(self):
        """检查GDS插件是否可用"""
        # 此检查将在实际调用时进行
        self.gds_available = False

    async def detect_communities_louvain(
        self,
        document_id: str,
        max_levels: int = 10,
        max_iterations: int = 10,
        tolerance: float = 0.0001,
    ) -> dict[str, Any]:
        """
        使用Louvain算法进行社区检测

        Args:
            document_id: 文档ID
            max_levels: 最大层级数
            max_iterations: 每层最大迭代次数
            tolerance: 收敛容差

        Returns:
            社区检测结果
        """
        start_time = datetime.now()
        graph_name = f"graph_{document_id}"

        try:
            logger.info(f"Starting Louvain community detection for document {document_id}")

            # 1. 创建图投影
            await self._create_graph_projection(graph_name, document_id)

            # 2. 运行Louvain算法
            communities = await self._run_louvain(
                graph_name, max_levels, max_iterations, tolerance
            )

            # 3. 计算模块度
            modularity_score = await self._calculate_modularity(graph_name)

            # 4. 将社区ID写回Neo4j
            await self._write_community_ids(communities)

            # 5. 清理图投影
            await self._drop_graph_projection(graph_name)

            duration = (datetime.now() - start_time).total_seconds()

            # 记录指标
            community_detection_total.labels(
                algorithm="louvain", status="success"
            ).inc()
            community_detection_duration.labels(algorithm="louvain").observe(duration)
            community_modularity.labels(
                document_id=document_id, algorithm="louvain"
            ).set(modularity_score)

            logger.info(
                f"Louvain detection completed: {len(communities)} communities, "
                f"modularity={modularity_score:.3f}, duration={duration:.2f}s"
            )

            return {
                "success": True,
                "document_id": document_id,
                "algorithm": "louvain",
                "communities_count": len(communities),
                "modularity": modularity_score,
                "duration_seconds": duration,
                "communities": communities,
            }

        except Exception as e:
            logger.error(f"Louvain community detection failed: {e}")
            community_detection_total.labels(
                algorithm="louvain", status="failure"
            ).inc()

            # 尝试清理图投影
            try:
                await self._drop_graph_projection(graph_name)
            except:
                pass

            raise CommunityDetectionError(
                f"Louvain detection failed: {e}", algorithm="louvain"
            )

    async def _create_graph_projection(self, graph_name: str, document_id: str):
        """创建图投影"""
        try:
            # 检查图是否已存在
            existing = await self.neo4j.execute_query(
                """
                CALL gds.graph.exists($graphName)
                YIELD exists
                RETURN exists
                """,
                {"graphName": graph_name},
            )

            if existing and existing[0]["exists"]:
                # 删除已存在的图
                await self._drop_graph_projection(graph_name)

            # 创建新的图投影
            await self.neo4j.execute_query(
                """
                CALL gds.graph.project(
                    $graphName,
                    {
                        Entity: {
                            label: 'Entity',
                            properties: {
                                document_id: {property: 'document_id'},
                                text: {property: 'text'},
                                label: {property: 'label'}
                            }
                        }
                    },
                    {
                        RELATES_TO: {
                            type: '*',
                            orientation: 'UNDIRECTED',
                            properties: {confidence: {property: 'confidence', defaultValue: 1.0}}
                        }
                    },
                    {
                        nodeProperties: ['document_id', 'text', 'label'],
                        relationshipProperties: ['confidence']
                    }
                )
                YIELD graphName, nodeCount, relationshipCount
                RETURN graphName, nodeCount, relationshipCount
                """,
                {"graphName": graph_name},
            )

            logger.debug(f"Graph projection {graph_name} created")

        except Exception as e:
            logger.error(f"Failed to create graph projection: {e}")
            # 尝试使用简化版本（不带高级特性）
            await self._create_simple_graph_projection(graph_name, document_id)

    async def _create_simple_graph_projection(
        self, graph_name: str, document_id: str
    ):
        """创建简化版图投影（兼容旧版Neo4j）"""
        await self.neo4j.execute_query(
            """
            CALL gds.graph.project(
                $graphName,
                'Entity',
                '*',
                {
                    nodeProperties: ['document_id'],
                    relationshipProperties: ['confidence']
                }
            )
            YIELD graphName, nodeCount, relationshipCount
            RETURN graphName, nodeCount, relationshipCount
            """,
            {"graphName": graph_name},
        )

    async def _run_louvain(
        self,
        graph_name: str,
        max_levels: int,
        max_iterations: int,
        tolerance: float,
    ) -> list[dict[str, Any]]:
        """运行Louvain算法"""
        results = await self.neo4j.execute_query(
            """
            CALL gds.louvain.stream(
                $graphName,
                {
                    maxLevels: $maxLevels,
                    maxIterations: $maxIterations,
                    tolerance: $tolerance,
                    includeIntermediateCommunities: true
                }
            )
            YIELD nodeId, communityId, intermediateCommunityIds
            RETURN gds.util.asNode(nodeId) AS entity,
                   communityId,
                   intermediateCommunityIds
            """,
            {
                "graphName": graph_name,
                "maxLevels": max_levels,
                "maxIterations": max_iterations,
                "tolerance": tolerance,
            },
        )

        # 按社区分组
        communities_map: dict[int, list[dict[str, Any]]] = {}

        for record in results:
            community_id = record["communityId"]
            entity_node = record["entity"]

            if community_id not in communities_map:
                communities_map[community_id] = []

            communities_map[community_id].append(
                {
                    "id": entity_node.element_id,
                    "text": entity_node.get("text", ""),
                    "label": entity_node.get("label", ""),
                    "intermediate_communities": record.get(
                        "intermediateCommunityIds", []
                    ),
                }
            )

        # 转换为列表格式
        communities = []
        for comm_id, entities in communities_map.items():
            communities.append(
                {
                    "id": f"community_{comm_id}",
                    "community_id": comm_id,
                    "size": len(entities),
                    "entities": entities,
                }
            )

        return communities

    async def _calculate_modularity(self, graph_name: str) -> float:
        """计算模块度"""
        try:
            result = await self.neo4j.execute_query(
                """
                CALL gds.louvain.stats(
                    $graphName
                )
                YIELD modularity
                RETURN modularity
                """,
                {"graphName": graph_name},
            )

            if result:
                return result[0]["modularity"]

            return 0.0

        except Exception as e:
            logger.warning(f"Failed to calculate modularity: {e}")
            return 0.0

    async def _write_community_ids(self, communities: list[dict[str, Any]]):
        """将社区ID写回Neo4j节点"""
        for community in communities:
            community_id = community["community_id"]

            for entity in community["entities"]:
                try:
                    await self.neo4j.execute_query(
                        """
                        MATCH (n)
                        WHERE elementId(n) = $entity_id
                        SET n.community_id = $community_id
                        """,
                        {"entity_id": entity["id"], "community_id": community_id},
                    )
                except Exception as e:
                    logger.warning(f"Failed to set community_id for entity: {e}")

    async def _drop_graph_projection(self, graph_name: str):
        """删除图投影"""
        try:
            await self.neo4j.execute_query(
                """
                CALL gds.graph.drop($graphName)
                YIELD graphName
                RETURN graphName
                """,
                {"graphName": graph_name},
            )
            logger.debug(f"Graph projection {graph_name} dropped")

        except Exception as e:
            logger.warning(f"Failed to drop graph projection: {e}")

    async def detect_communities_fallback(
        self, document_id: str
    ) -> dict[str, Any]:
        """降级方案：使用简单的连通分量算法"""
        start_time = datetime.now()

        try:
            logger.warning(
                f"Using fallback community detection (connected components) for {document_id}"
            )

            # 使用连通分量算法
            results = await self.neo4j.execute_query(
                """
                MATCH (n:Entity {document_id: $document_id})
                CALL apoc.path.spanningTree(n, {
                    relationshipFilter: '*',
                    minLevel: 0,
                    maxLevel: 100
                })
                YIELD path
                WITH collect(DISTINCT nodes(path)) as component
                RETURN component, size(component) as size
                ORDER BY size DESC
                """,
                {"document_id": document_id},
            )

            communities = []
            for idx, record in enumerate(results):
                entities = record["component"]
                communities.append(
                    {
                        "id": f"community_{idx}",
                        "community_id": idx,
                        "size": record["size"],
                        "entities": [
                            {
                                "id": e.element_id,
                                "text": e.get("text", ""),
                                "label": e.get("label", ""),
                            }
                            for e in entities
                        ],
                    }
                )

            duration = (datetime.now() - start_time).total_seconds()

            community_detection_total.labels(
                algorithm="connected_components", status="success"
            ).inc()
            community_detection_duration.labels(
                algorithm="connected_components"
            ).observe(duration)

            return {
                "success": True,
                "document_id": document_id,
                "algorithm": "connected_components",
                "communities_count": len(communities),
                "duration_seconds": duration,
                "communities": communities,
            }

        except Exception as e:
            logger.error(f"Fallback community detection failed: {e}")
            community_detection_total.labels(
                algorithm="connected_components", status="failure"
            ).inc()
            raise CommunityDetectionError(
                f"Fallback detection failed: {e}", algorithm="connected_components"
            )


# 全局实例
_community_detection_gds: CommunityDetectionGDS | None = None


def get_community_detection_gds(neo4j_client) -> CommunityDetectionGDS:
    """
    获取社区检测GDS服务实例（单例）

    Args:
        neo4j_client: Neo4j客户端

    Returns:
        CommunityDetectionGDS实例
    """
    global _community_detection_gds

    if _community_detection_gds is None:
        _community_detection_gds = CommunityDetectionGDS(neo4j_client)

    return _community_detection_gds
