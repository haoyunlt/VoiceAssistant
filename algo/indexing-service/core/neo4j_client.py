"""
Neo4j Client - Knowledge graph operations
"""

import logging
from typing import Any

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j graph database client"""

    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logger.info(f"Connected to Neo4j at {uri}")

    def close(self):
        """Close connection"""
        self.driver.close()

    def create_document_node(self, document_id: str, properties: dict[str, Any]):
        """Create document node"""
        with self.driver.session() as session:
            query = """
            MERGE (d:Document {id: $document_id})
            SET d += $properties
            RETURN d
            """
            session.run(query, document_id=document_id, properties=properties)
            logger.info(f"Created document node: {document_id}")

    def create_chunk_node(self, chunk_id: str, document_id: str, properties: dict[str, Any]):
        """Create chunk node and link to document"""
        with self.driver.session() as session:
            query = """
            MATCH (d:Document {id: $document_id})
            MERGE (c:Chunk {id: $chunk_id})
            SET c += $properties
            MERGE (d)-[:HAS_CHUNK]->(c)
            RETURN c
            """
            session.run(query, chunk_id=chunk_id, document_id=document_id, properties=properties)

    def create_entity_node(
        self, entity_name: str, entity_type: str, properties: dict[str, Any] = None
    ):
        """Create entity node"""
        with self.driver.session() as session:
            props = properties or {}
            props["type"] = entity_type

            query = """
            MERGE (e:Entity {name: $entity_name})
            SET e += $properties
            RETURN e
            """
            session.run(query, entity_name=entity_name, properties=props)

    def create_relationship(
        self, from_id: str, to_id: str, rel_type: str, properties: dict[str, Any] = None
    ):
        """Create relationship between nodes"""
        with self.driver.session() as session:
            props = properties or {}

            query = f"""
            MATCH (a {{id: $from_id}})
            MATCH (b {{id: $to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $properties
            RETURN r
            """
            session.run(query, from_id=from_id, to_id=to_id, properties=props)

    def link_chunk_to_entity(self, chunk_id: str, entity_name: str, relation: str = "MENTIONS"):
        """Link chunk to entity"""
        with self.driver.session() as session:
            query = f"""
            MATCH (c:Chunk {{id: $chunk_id}})
            MATCH (e:Entity {{name: $entity_name}})
            MERGE (c)-[r:{relation}]->(e)
            RETURN r
            """
            session.run(query, chunk_id=chunk_id, entity_name=entity_name)

    def search_related(self, entity_name: str, tenant_id: str, limit: int = 10) -> list[dict]:
        """Search related chunks by entity"""
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $entity_name})
            MATCH (c:Chunk)-[:MENTIONS]->(e)
            MATCH (d:Document)-[:HAS_CHUNK]->(c)
            WHERE d.tenant_id = $tenant_id
            RETURN c.id as chunk_id, c.content as content, d.id as document_id
            LIMIT $limit
            """
            result = session.run(query, entity_name=entity_name, tenant_id=tenant_id, limit=limit)

            chunks = []
            for record in result:
                chunks.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "content": record["content"],
                        "document_id": record["document_id"],
                        "method": "graph",
                    }
                )

            return chunks

    def build_graph_from_document(self, document_id: str, chunks: list[dict], tenant_id: str):
        """Build knowledge graph from document chunks"""
        logger.info(f"Building graph for document: {document_id}")

        # Create document node
        self.create_document_node(document_id, {"tenant_id": tenant_id, "chunk_count": len(chunks)})

        # Process each chunk
        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            content = chunk["content"]

            # Create chunk node
            self.create_chunk_node(
                chunk_id,
                document_id,
                {
                    "content": content[:500],  # Store preview
                    "token_count": chunk.get("token_count", 0),
                },
            )

            # Extract entities (simplified - in production use NER)
            entities = self._extract_entities(content)

            # Create entity nodes and relationships
            for entity in entities:
                self.create_entity_node(entity["name"], entity["type"])
                self.link_chunk_to_entity(chunk_id, entity["name"])

        # Create chunk sequence relationships
        for i in range(len(chunks) - 1):
            self.create_relationship(chunks[i]["chunk_id"], chunks[i + 1]["chunk_id"], "NEXT")

        logger.info(f"Graph built for document {document_id}: {len(chunks)} chunks")

    def _extract_entities(self, text: str) -> list[dict]:
        """Extract entities from text (simplified)"""
        # In production, use spaCy or other NER models
        # For now, extract capitalized words as potential entities
        words = text.split()
        entities = []

        for word in words:
            # Simple heuristic: capitalized words
            if word and word[0].isupper() and len(word) > 3:
                entities.append({"name": word.strip(".,!?;:"), "type": "UNKNOWN"})

        # Remove duplicates
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity["name"] not in seen:
                seen.add(entity["name"])
                unique_entities.append(entity)

        return unique_entities[:10]  # Limit to top 10

    def delete_document_graph(self, document_id: str):
        """Delete document and all related nodes"""
        with self.driver.session() as session:
            query = """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE d, c
            """
            session.run(query, document_id=document_id)
            logger.info(f"Deleted graph for document: {document_id}")
