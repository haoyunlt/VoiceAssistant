"""
Hybrid Retriever - Combine vector, BM25 and graph retrieval
"""

import logging
from typing import List, Dict
import numpy as np

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval combining multiple strategies"""
    
    def __init__(self, milvus_client, neo4j_client, embedder):
        self.milvus = milvus_client
        self.neo4j = neo4j_client
        self.embedder = embedder
    
    def retrieve(self, query: str, tenant_id: str, top_k: int = 20, mode: str = "hybrid") -> List[Dict]:
        """Retrieve documents using hybrid approach"""
        
        if mode == "vector":
            return self._vector_retrieval(query, tenant_id, top_k)
        elif mode == "graph":
            return self._graph_retrieval(query, tenant_id, top_k)
        elif mode == "hybrid":
            return self._hybrid_retrieval(query, tenant_id, top_k)
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def _vector_retrieval(self, query: str, tenant_id: str, top_k: int) -> List[Dict]:
        """Vector similarity search"""
        logger.info(f"Vector retrieval for query: {query[:50]}...")
        
        # Generate query embedding
        query_embedding = self.embedder.encode_single(query)
        
        # Search in Milvus
        results = self.milvus.search(
            query_vectors=[query_embedding.tolist()],
            tenant_id=tenant_id,
            top_k=top_k
        )
        
        # Format results
        retrieved = []
        for hits in results:
            for hit in hits:
                retrieved.append({
                    'chunk_id': hit.entity.get('chunk_id'),
                    'document_id': hit.entity.get('document_id'),
                    'content': hit.entity.get('content'),
                    'score': hit.score,
                    'method': 'vector'
                })
        
        return retrieved
    
    def _graph_retrieval(self, query: str, tenant_id: str, top_k: int) -> List[Dict]:
        """Graph-based retrieval"""
        logger.info(f"Graph retrieval for query: {query[:50]}...")
        
        # Extract entities from query (simplified)
        entities = self._extract_entities(query)
        
        # Search in Neo4j
        retrieved = []
        for entity in entities:
            results = self.neo4j.search_related(entity, tenant_id, limit=top_k // len(entities))
            retrieved.extend(results)
        
        return retrieved[:top_k]
    
    def _hybrid_retrieval(self, query: str, tenant_id: str, top_k: int) -> List[Dict]:
        """Hybrid retrieval with RRF fusion"""
        logger.info(f"Hybrid retrieval for query: {query[:50]}...")
        
        # Retrieve from multiple sources
        vector_results = self._vector_retrieval(query, tenant_id, top_k * 2)
        graph_results = self._graph_retrieval(query, tenant_id, top_k)
        
        # Reciprocal Rank Fusion (RRF)
        fused_results = self._rrf_fusion([vector_results, graph_results], k=60)
        
        return fused_results[:top_k]
    
    def _rrf_fusion(self, result_lists: List[List[Dict]], k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion"""
        scores = {}
        
        for results in result_lists:
            for rank, result in enumerate(results, start=1):
                chunk_id = result['chunk_id']
                if chunk_id not in scores:
                    scores[chunk_id] = {
                        'result': result,
                        'score': 0
                    }
                scores[chunk_id]['score'] += 1 / (k + rank)
        
        # Sort by RRF score
        sorted_results = sorted(
            scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return [item['result'] for item in sorted_results]
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query (simplified)"""
        # In production, use NER model
        words = query.split()
        # Simple heuristic: capitalize words as potential entities
        entities = [w for w in words if w[0].isupper()]
        return entities if entities else [query]


class Reranker:
    """Rerank retrieved documents"""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, documents: List[Dict], top_k: int = 10) -> List[Dict]:
        """Rerank documents using cross-encoder"""
        if not documents:
            return []
        
        # Prepare pairs
        pairs = [[query, doc['content']] for doc in documents]
        
        # Get scores
        scores = self.model.predict(pairs)
        
        # Add scores and sort
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        # Sort by rerank score
        reranked = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        
        return reranked[:top_k]

