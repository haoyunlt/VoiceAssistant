"""
Indexing Processor - Orchestrate the complete indexing pipeline
"""

import logging
import time

from .document_parser import DocumentChunker, DocumentParser
from .embedder import Embedder
from .milvus_client import MilvusClient
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class IndexingProcessor:
    """Complete document indexing pipeline"""

    def __init__(
        self,
        milvus_client: MilvusClient,
        neo4j_client: Neo4jClient,
        embedder: Embedder,
        minio_endpoint: str,
        minio_access_key: str,
        minio_secret_key: str,
    ):
        self.milvus = milvus_client
        self.neo4j = neo4j_client
        self.embedder = embedder
        self.parser = DocumentParser()
        self.chunker = DocumentChunker()
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key

    async def process_document(self, event: dict):
        """Process document uploaded event"""
        try:
            logger.info(f"Processing document: {event.get('document_id')}")
            start_time = time.time()

            # Extract event data
            document_id = event.get("document_id")
            storage_path = event.get("storage_path")
            content_type = event.get("content_type")
            tenant_id = event.get("tenant_id")

            # 1. Download file from MinIO
            logger.info(f"Downloading file from: {storage_path}")
            file_content = await self._download_file(storage_path)

            # 2. Parse document
            logger.info(f"Parsing document, content type: {content_type}")
            text = self.parser.parse(file_content, content_type)
            logger.info(f"Parsed text length: {len(text)} characters")

            # 3. Chunk document
            logger.info("Chunking document...")
            chunks = self.chunker.chunk_by_tokens(text, chunk_size=512, overlap=50)
            logger.info(f"Created {len(chunks)} chunks")

            # 4. Generate embeddings
            logger.info("Generating embeddings...")
            texts = [chunk["content"] for chunk in chunks]
            embeddings = self.embedder.encode(texts)
            logger.info(f"Generated {len(embeddings)} embeddings")

            # 5. Store in Milvus
            logger.info("Storing vectors in Milvus...")
            milvus_data = []
            for i, chunk in enumerate(chunks):
                milvus_data.append(
                    {
                        "chunk_id": f"{document_id}_chunk_{i}",
                        "document_id": document_id,
                        "content": chunk["content"],
                        "embedding": embeddings[i].tolist(),
                        "tenant_id": tenant_id,
                        "created_at": int(time.time()),
                    }
                )

            self.milvus.insert(milvus_data)
            logger.info(f"Stored {len(milvus_data)} vectors in Milvus")

            # 6. Build knowledge graph
            logger.info("Building knowledge graph in Neo4j...")
            graph_chunks = [
                {
                    "chunk_id": d["chunk_id"],
                    "content": d["content"],
                    "token_count": chunks[i].get("token_count", 0),
                }
                for i, d in enumerate(milvus_data)
            ]
            self.neo4j.build_graph_from_document(document_id, graph_chunks, tenant_id)
            logger.info("Knowledge graph built successfully")

            # 7. Calculate metrics
            duration = time.time() - start_time
            logger.info(f"Document indexed successfully in {duration:.2f}s")

            # Return success metrics
            return {
                "success": True,
                "document_id": document_id,
                "chunk_count": len(chunks),
                "vector_count": len(embeddings),
                "graph_node_count": len(chunks) * 2,  # Chunks + Document
                "duration_seconds": duration,
            }

        except Exception as e:
            logger.error(f"Error processing document: {e}", exc_info=True)
            return {"success": False, "document_id": event.get("document_id"), "error": str(e)}

    async def _download_file(self, storage_path: str) -> bytes:
        """Download file from MinIO"""
        # In production, use MinIO client
        # For now, simulate download

        # Construct MinIO URL
        # url = f"http://{self.minio_endpoint}/{storage_path}"

        # For demo, return mock content
        logger.info(f"[MOCK] Downloaded file from: {storage_path}")
        return b"Mock document content for testing"

    async def delete_document(self, document_id: str):
        """Delete document from all indexes"""
        try:
            logger.info(f"Deleting document: {document_id}")

            # Delete from Milvus
            self.milvus.delete_by_document(document_id)

            # Delete from Neo4j
            self.neo4j.delete_document_graph(document_id)

            logger.info(f"Document deleted successfully: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting document: {e}", exc_info=True)
            return False
