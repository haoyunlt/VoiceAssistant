"""
Milvus Client - Vector database operations
"""

import logging
from typing import List, Dict
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus vector database client"""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        self.host = host
        self.port = port
        self.collection = None
        self.connect()
    
    def connect(self):
        """Connect to Milvus"""
        try:
            connections.connect("default", host=self.host, port=self.port)
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def create_collection(self, collection_name: str, dim: int = 1024):
        """Create collection if not exists"""
        if utility.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            self.collection = Collection(collection_name)
            return
        
        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        
        schema = CollectionSchema(fields=fields, description="Document chunks")
        self.collection = Collection(name=collection_name, schema=schema)
        
        # Create index
        index_params = {
            "metric_type": "IP",  # Inner Product (Cosine Similarity)
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        
        logger.info(f"Created collection {collection_name} with HNSW index")
    
    def insert(self, data: List[Dict]):
        """Insert vectors into collection"""
        if not self.collection:
            raise ValueError("Collection not initialized")
        
        # Prepare data
        chunk_ids = [d['chunk_id'] for d in data]
        document_ids = [d['document_id'] for d in data]
        contents = [d['content'] for d in data]
        embeddings = [d['embedding'] for d in data]
        tenant_ids = [d['tenant_id'] for d in data]
        created_ats = [d['created_at'] for d in data]
        
        entities = [
            chunk_ids,
            document_ids,
            contents,
            embeddings,
            tenant_ids,
            created_ats
        ]
        
        mr = self.collection.insert(entities)
        self.collection.flush()
        logger.info(f"Inserted {len(data)} vectors")
        return mr
    
    def search(self, query_vectors: List[List[float]], tenant_id: str, top_k: int = 10):
        """Search similar vectors"""
        if not self.collection:
            raise ValueError("Collection not initialized")
        
        # Load collection to memory
        self.collection.load()
        
        search_params = {
            "metric_type": "IP",
            "params": {"ef": 128}
        }
        
        # Search with filter
        results = self.collection.search(
            data=query_vectors,
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=f"tenant_id == '{tenant_id}'",
            output_fields=["chunk_id", "document_id", "content"]
        )
        
        return results
    
    def delete_by_document(self, document_id: str):
        """Delete vectors by document ID"""
        if not self.collection:
            raise ValueError("Collection not initialized")
        
        expr = f"document_id == '{document_id}'"
        self.collection.delete(expr)
        logger.info(f"Deleted vectors for document {document_id}")
    
    def close(self):
        """Close connection"""
        connections.disconnect("default")

