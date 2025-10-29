"""
BM25 Retriever - Traditional keyword-based retrieval
"""

import logging

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25 keyword-based retrieval"""

    def __init__(self):
        self.corpus = []
        self.corpus_metadata = []
        self.bm25 = None

    def index_documents(self, documents: list[dict]):
        """Index documents for BM25 search"""
        logger.info(f"Indexing {len(documents)} documents for BM25...")

        # Extract text and metadata
        self.corpus = [doc['content'] for doc in documents]
        self.corpus_metadata = [
            {
                'chunk_id': doc.get('chunk_id'),
                'document_id': doc.get('document_id'),
                'content': doc['content']
            }
            for doc in documents
        ]

        # Tokenize corpus
        tokenized_corpus = [doc.lower().split() for doc in self.corpus]

        # Create BM25 index
        self.bm25 = BM25Okapi(tokenized_corpus)

        logger.info(f"BM25 index created with {len(self.corpus)} documents")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search using BM25"""
        if not self.bm25:
            logger.warning("BM25 index not initialized")
            return []

        # Tokenize query
        tokenized_query = query.lower().split()

        # Get scores
        scores = self.bm25.get_scores(tokenized_query)

        # Get top k results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include results with positive scores
                result = self.corpus_metadata[idx].copy()
                result['score'] = float(scores[idx])
                result['method'] = 'bm25'
                results.append(result)

        logger.info(f"BM25 search returned {len(results)} results")
        return results

    def get_corpus_size(self) -> int:
        """Get corpus size"""
        return len(self.corpus)

