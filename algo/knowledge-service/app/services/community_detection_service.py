"""
社区检测服务
实现 Leiden 和 Louvain 算法
"""

import logging

logger = logging.getLogger(__name__)


class CommunityDetectionService:
    """社区检测服务"""

    def __init__(self, neo4j_client):
        """
        初始化社区检测服务

        Args:
            neo4j_client: Neo4j客户端
        """
        self.neo4j = neo4j_client
        logger.info("CommunityDetectionService initialized")

    async def detect_communities_leiden(
        self,
        max_iterations: int = 10,
        resolution: float = 1.0,
        randomness: float = 0.001,
    ) -> dict:
        """
        使用Leiden算法检测社区

        Leiden算法是Louvain算法的改进版本，能更好地保证连通性。

        Args:
            max_iterations: 最大迭代次数
            resolution: 分辨率参数（控制社区大小）
            randomness: 随机性参数

        Returns:
            社区检测结果
        """
        logger.info(
            f"Running Leiden algorithm: "
            f"max_iterations={max_iterations}, "
            f"resolution={resolution}"
        )

        try:
            # 使用Neo4j的GDS库执行Leiden算法
            cypher = """
            CALL gds.leiden.stream('myGraph', {
                maxIterations: $max_iterations,
                gamma: $resolution,
                theta: $randomness
            })
            YIELD nodeId, communityId, intermediateCommunityIds
            WITH gds.util.asNode(nodeId) AS node, communityId
            RETURN
                node.name AS entity_name,
                node.type AS entity_type,
                communityId,
                COUNT(*) OVER (PARTITION BY communityId) AS community_size
            ORDER BY communityId, entity_name
            """

            results = await self.neo4j.query(
                cypher,
                {
                    "max_iterations": max_iterations,
                    "resolution": resolution,
                    "randomness": randomness,
                },
            )

            # 组织结果
            communities = {}
            for r in results:
                comm_id = r["communityId"]
                if comm_id not in communities:
                    communities[comm_id] = {
                        "community_id": comm_id,
                        "size": r["community_size"],
                        "entities": [],
                    }
                communities[comm_id]["entities"].append(
                    {"name": r["entity_name"], "type": r.get("entity_type")}
                )

            community_list = list(communities.values())

            logger.info(f"Leiden detected {len(community_list)} communities")

            return {
                "algorithm": "leiden",
                "communities": community_list,
                "total_communities": len(community_list),
                "parameters": {
                    "max_iterations": max_iterations,
                    "resolution": resolution,
                    "randomness": randomness,
                },
            }

        except Exception as e:
            logger.error(f"Leiden algorithm failed: {e}", exc_info=True)
            return {
                "algorithm": "leiden",
                "communities": [],
                "total_communities": 0,
                "error": str(e),
            }

    async def detect_communities_louvain(
        self,
        max_iterations: int = 10,
        tolerance: float = 0.0001,
    ) -> dict:
        """
        使用Louvain算法检测社区

        Louvain算法是经典的模块度优化算法。

        Args:
            max_iterations: 最大迭代次数
            tolerance: 收敛容差

        Returns:
            社区检测结果
        """
        logger.info(
            f"Running Louvain algorithm: " f"max_iterations={max_iterations}"
        )

        try:
            # 使用Neo4j的GDS库执行Louvain算法
            cypher = """
            CALL gds.louvain.stream('myGraph', {
                maxIterations: $max_iterations,
                tolerance: $tolerance
            })
            YIELD nodeId, communityId, intermediateCommunityIds
            WITH gds.util.asNode(nodeId) AS node, communityId
            RETURN
                node.name AS entity_name,
                node.type AS entity_type,
                communityId,
                COUNT(*) OVER (PARTITION BY communityId) AS community_size
            ORDER BY communityId, entity_name
            """

            results = await self.neo4j.query(
                cypher, {"max_iterations": max_iterations, "tolerance": tolerance}
            )

            # 组织结果
            communities = {}
            for r in results:
                comm_id = r["communityId"]
                if comm_id not in communities:
                    communities[comm_id] = {
                        "community_id": comm_id,
                        "size": r["community_size"],
                        "entities": [],
                    }
                communities[comm_id]["entities"].append(
                    {"name": r["entity_name"], "type": r.get("entity_type")}
                )

            community_list = list(communities.values())

            logger.info(f"Louvain detected {len(community_list)} communities")

            return {
                "algorithm": "louvain",
                "communities": community_list,
                "total_communities": len(community_list),
                "parameters": {
                    "max_iterations": max_iterations,
                    "tolerance": tolerance,
                },
            }

        except Exception as e:
            logger.error(f"Louvain algorithm failed: {e}", exc_info=True)
            return {
                "algorithm": "louvain",
                "communities": [],
                "total_communities": 0,
                "error": str(e),
            }

    async def generate_community_summary(
        self, community_id: int, llm_service=None
    ) -> dict:
        """
        生成社区摘要

        使用LLM生成社区的自然语言描述

        Args:
            community_id: 社区ID
            llm_service: LLM服务（可选）

        Returns:
            社区摘要
        """
        logger.info(f"Generating summary for community {community_id}")

        try:
            # 获取社区实体和关系
            cypher = """
            MATCH (n)
            WHERE n.community_id = $community_id
            WITH collect(n) AS nodes
            UNWIND nodes AS n1
            UNWIND nodes AS n2
            MATCH (n1)-[r]->(n2)
            RETURN
                collect(DISTINCT {name: n1.name, type: n1.type}) AS entities,
                collect(DISTINCT {
                    source: n1.name,
                    target: n2.name,
                    type: type(r),
                    context: r.context
                }) AS relations
            LIMIT 1
            """

            result = await self.neo4j.query(cypher, {"community_id": community_id})

            if not result:
                return {
                    "community_id": community_id,
                    "summary": "Community not found",
                }

            entities = result[0].get("entities", [])
            relations = result[0].get("relations", [])

            # 如果有LLM服务，生成摘要
            if llm_service:
                summary = await self._generate_llm_summary(
                    entities, relations, llm_service
                )
            else:
                # 简单摘要
                entity_types = {}
                for e in entities:
                    entity_type = e.get("type", "Unknown")
                    entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

                summary = (
                    f"Community contains {len(entities)} entities "
                    f"and {len(relations)} relations. "
                    f"Entity types: {entity_types}"
                )

            return {
                "community_id": community_id,
                "summary": summary,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "entity_types": entity_types if not llm_service else None,
            }

        except Exception as e:
            logger.error(f"Failed to generate community summary: {e}", exc_info=True)
            return {"community_id": community_id, "error": str(e)}

    async def _generate_llm_summary(
        self, entities: list[dict], relations: list[dict], llm_service
    ) -> str:
        """
        使用LLM生成社区摘要

        Args:
            entities: 实体列表
            relations: 关系列表
            llm_service: LLM服务

        Returns:
            摘要文本
        """
        import json

        prompt = f"""
请为以下知识社区生成一个简洁的摘要（不超过100字）：

实体列表:
{json.dumps(entities[:20], ensure_ascii=False, indent=2)}  # 限制实体数量

关系列表:
{json.dumps(relations[:20], ensure_ascii=False, indent=2)}  # 限制关系数量

请描述这个社区的主题、核心概念和知识结构。
"""

        try:
            response = await llm_service.chat(
                messages=[
                    {"role": "system", "content": "你是一个知识图谱分析专家"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return f"Failed to generate summary: {str(e)}"

    async def create_graph_projection(
        self,
        projection_name: str = "myGraph",
        node_label: str = "Entity",
        relationship_type: str = "RELATES",
    ) -> dict:
        """
        创建图投影（用于GDS算法）

        Args:
            projection_name: 投影名称
            node_label: 节点标签
            relationship_type: 关系类型

        Returns:
            创建结果
        """
        logger.info(f"Creating graph projection: {projection_name}")

        try:
            # 检查投影是否已存在
            check_cypher = """
            CALL gds.graph.exists($projection_name)
            YIELD exists
            RETURN exists
            """

            check_result = await self.neo4j.query(
                check_cypher, {"projection_name": projection_name}
            )

            if check_result and check_result[0].get("exists"):
                logger.info(f"Graph projection {projection_name} already exists")
                return {"status": "exists", "projection_name": projection_name}

            # 创建图投影
            create_cypher = f"""
            CALL gds.graph.project(
                $projection_name,
                '{node_label}',
                '{relationship_type}'
            )
            YIELD graphName, nodeCount, relationshipCount
            RETURN graphName, nodeCount, relationshipCount
            """

            result = await self.neo4j.query(
                create_cypher, {"projection_name": projection_name}
            )

            if result:
                return {
                    "status": "created",
                    "projection_name": result[0]["graphName"],
                    "node_count": result[0]["nodeCount"],
                    "relationship_count": result[0]["relationshipCount"],
                }

            return {"status": "failed", "error": "No result returned"}

        except Exception as e:
            logger.error(f"Failed to create graph projection: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def drop_graph_projection(self, projection_name: str = "myGraph") -> dict:
        """
        删除图投影

        Args:
            projection_name: 投影名称

        Returns:
            删除结果
        """
        logger.info(f"Dropping graph projection: {projection_name}")

        try:
            cypher = """
            CALL gds.graph.drop($projection_name)
            YIELD graphName
            RETURN graphName
            """

            result = await self.neo4j.query(cypher, {"projection_name": projection_name})

            if result:
                return {"status": "dropped", "projection_name": result[0]["graphName"]}

            return {"status": "not_found"}

        except Exception as e:
            logger.error(f"Failed to drop graph projection: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
