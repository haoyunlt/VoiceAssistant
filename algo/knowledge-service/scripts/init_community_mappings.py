#!/usr/bin/env python3
"""
初始化实体-社区映射关系

此脚本用于为现有图谱建立实体与社区的映射关系。
运行条件：
1. Neo4j 中已有实体节点
2. 已执行社区检测（生成 community_id 属性）
3. 需要建立 BELONGS_TO 关系

使用方法：
    python scripts/init_community_mappings.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph.neo4j_client import Neo4jClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def init_community_mappings():
    """初始化实体-社区映射"""
    
    # 1. 连接 Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    logger.info(f"Connecting to Neo4j: {neo4j_uri}")
    
    neo4j_client = Neo4jClient(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )
    
    try:
        # 2. 检查是否已存在社区节点
        check_query = """
        MATCH (c:Community)
        RETURN count(c) as community_count
        """
        
        result = await neo4j_client.execute_query(check_query)
        community_count = result[0]["community_count"] if result else 0
        
        logger.info(f"Found {community_count} existing Community nodes")
        
        if community_count == 0:
            logger.warning("No Community nodes found. Creating community structure...")
            
            # 3. 如果没有社区节点，基于 community_id 属性创建
            create_communities_query = """
            MATCH (e:Entity)
            WHERE e.community_id IS NOT NULL
            WITH DISTINCT e.community_id as cid
            MERGE (c:Community {id: 'community_' + toString(cid)})
            ON CREATE SET
                c.created_at = datetime(),
                c.summary = 'Auto-generated community',
                c.entity_count = 0
            RETURN count(c) as created_count
            """
            
            result = await neo4j_client.execute_query(create_communities_query)
            created_count = result[0]["created_count"] if result else 0
            logger.info(f"Created {created_count} Community nodes")
        
        # 4. 建立 BELONGS_TO 关系
        logger.info("Creating BELONGS_TO relationships...")
        
        mapping_query = """
        MATCH (e:Entity)
        WHERE e.community_id IS NOT NULL
        MATCH (c:Community {id: 'community_' + toString(e.community_id)})
        MERGE (e)-[:BELONGS_TO]->(c)
        RETURN count(*) as mapping_count
        """
        
        result = await neo4j_client.execute_query(mapping_query)
        mapping_count = result[0]["mapping_count"] if result else 0
        
        logger.info(f"Created {mapping_count} BELONGS_TO relationships")
        
        # 5. 更新社区的实体计数
        update_count_query = """
        MATCH (c:Community)<-[:BELONGS_TO]-(e:Entity)
        WITH c, count(e) as entity_count
        SET c.entity_count = entity_count
        RETURN c.id as community_id, entity_count
        """
        
        result = await neo4j_client.execute_query(update_count_query)
        
        logger.info("Community entity counts updated:")
        for row in result[:10]:  # 显示前 10 个
            logger.info(f"  {row['community_id']}: {row['entity_count']} entities")
        
        # 6. 验证
        verify_query = """
        MATCH (e:Entity)-[:BELONGS_TO]->(c:Community)
        RETURN count(DISTINCT e) as mapped_entities,
               count(DISTINCT c) as communities
        """
        
        result = await neo4j_client.execute_query(verify_query)
        if result:
            logger.info(
                f"Verification: {result[0]['mapped_entities']} entities "
                f"mapped to {result[0]['communities']} communities"
            )
        
        logger.info("✅ Community mapping initialization complete!")
        
    except Exception as e:
        logger.error(f"Failed to initialize community mappings: {e}", exc_info=True)
        raise
    
    finally:
        await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(init_community_mappings())

