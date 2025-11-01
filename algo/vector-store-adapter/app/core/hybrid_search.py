"""Hybrid search implementation combining vector and BM25"""

import logging

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search combining vector similarity and BM25 text matching

    Features:
    - Vector similarity search
    - BM25 keyword matching
    - RRF (Reciprocal Rank Fusion) for result merging
    - Weighted score fusion
    """

    def __init__(self):
        """Initialize hybrid search engine"""
        pass

    @staticmethod
    def reciprocal_rank_fusion(
        vector_results: list[dict],
        bm25_results: list[dict],
        k: int = 60,
        vector_weight: float = 0.5,
    ) -> list[dict]:
        """
        Merge results using Reciprocal Rank Fusion (RRF)

        RRF formula: score(d) = sum(1 / (k + rank(d)))

        Args:
            vector_results: Results from vector search (with 'chunk_id' and 'score')
            bm25_results: Results from BM25 search (with 'chunk_id' and 'score')
            k: RRF constant (default: 60)
            vector_weight: Weight for vector results vs BM25 (0-1)

        Returns:
            Merged and re-ranked results
        """
        # Build rank maps
        vector_ranks = {item["chunk_id"]: idx for idx, item in enumerate(vector_results)}
        bm25_ranks = {item["chunk_id"]: idx for idx, item in enumerate(bm25_results)}

        # Build document maps for metadata
        vector_docs = {item["chunk_id"]: item for item in vector_results}
        bm25_docs = {item["chunk_id"]: item for item in bm25_results}

        # Get all unique document IDs
        all_chunk_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())

        # Calculate RRF scores
        rrf_scores = {}
        for chunk_id in all_chunk_ids:
            vector_rank = vector_ranks.get(chunk_id, len(vector_results))
            bm25_rank = bm25_ranks.get(chunk_id, len(bm25_results))

            # RRF formula with weights
            vector_rrf = vector_weight / (k + vector_rank)
            bm25_rrf = (1 - vector_weight) / (k + bm25_rank)

            rrf_scores[chunk_id] = vector_rrf + bm25_rrf

        # Sort by RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build final results with metadata
        results = []
        for chunk_id in sorted_chunk_ids:
            # Prefer vector result metadata, fallback to BM25
            doc = vector_docs.get(chunk_id, bm25_docs.get(chunk_id, {}))

            # Add RRF score and source info
            result = {
                **doc,
                "rrf_score": rrf_scores[chunk_id],
                "in_vector_results": chunk_id in vector_ranks,
                "in_bm25_results": chunk_id in bm25_ranks,
            }

            if chunk_id in vector_ranks:
                result["vector_rank"] = vector_ranks[chunk_id]
            if chunk_id in bm25_ranks:
                result["bm25_rank"] = bm25_ranks[chunk_id]

            results.append(result)

        return results

    @staticmethod
    def weighted_fusion(
        vector_results: list[dict],
        bm25_results: list[dict],
        vector_weight: float = 0.7,
    ) -> list[dict]:
        """
        Merge results using weighted score fusion

        Formula: score(d) = α * vector_score(d) + (1-α) * bm25_score(d)

        Args:
            vector_results: Results from vector search (with 'chunk_id' and 'score')
            bm25_results: Results from BM25 search (with 'chunk_id' and 'score')
            vector_weight: Weight for vector results (0-1), default: 0.7

        Returns:
            Merged and re-ranked results
        """

        # Normalize scores to [0, 1]
        def normalize_scores(results):
            if not results:
                return {}
            scores = [r["score"] for r in results]
            min_score = min(scores)
            max_score = max(scores)
            if max_score == min_score:
                return {r["chunk_id"]: 0.5 for r in results}
            return {
                r["chunk_id"]: (r["score"] - min_score) / (max_score - min_score) for r in results
            }

        vector_norm_scores = normalize_scores(vector_results)
        bm25_norm_scores = normalize_scores(bm25_results)

        # Build document maps
        vector_docs = {item["chunk_id"]: item for item in vector_results}
        bm25_docs = {item["chunk_id"]: item for item in bm25_results}

        # Get all unique document IDs
        all_chunk_ids = set(vector_norm_scores.keys()) | set(bm25_norm_scores.keys())

        # Calculate weighted scores
        weighted_scores = {}
        for chunk_id in all_chunk_ids:
            vector_score = vector_norm_scores.get(chunk_id, 0)
            bm25_score = bm25_norm_scores.get(chunk_id, 0)

            weighted_scores[chunk_id] = (
                vector_weight * vector_score + (1 - vector_weight) * bm25_score
            )

        # Sort by weighted score
        sorted_chunk_ids = sorted(
            weighted_scores.keys(), key=lambda x: weighted_scores[x], reverse=True
        )

        # Build final results
        results = []
        for chunk_id in sorted_chunk_ids:
            doc = vector_docs.get(chunk_id, bm25_docs.get(chunk_id, {}))

            result = {
                **doc,
                "weighted_score": weighted_scores[chunk_id],
                "in_vector_results": chunk_id in vector_norm_scores,
                "in_bm25_results": chunk_id in bm25_norm_scores,
            }

            if chunk_id in vector_norm_scores:
                result["vector_score_norm"] = vector_norm_scores[chunk_id]
            if chunk_id in bm25_norm_scores:
                result["bm25_score_norm"] = bm25_norm_scores[chunk_id]

            results.append(result)

        return results

    @staticmethod
    def build_bm25_index(documents: list[dict], content_field: str = "content") -> BM25Okapi:
        """
        Build BM25 index from documents

        Args:
            documents: List of documents with content field
            content_field: Field name containing text content

        Returns:
            BM25Okapi index
        """
        # Extract and tokenize documents
        corpus = []
        for doc in documents:
            content = doc.get(content_field, "")
            # Simple tokenization (you may want to use a proper tokenizer)
            tokens = content.lower().split()
            corpus.append(tokens)

        # Build BM25 index
        bm25 = BM25Okapi(corpus)
        return bm25

    @staticmethod
    def bm25_search(
        bm25_index: BM25Okapi,
        documents: list[dict],
        query: str,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Perform BM25 search

        Args:
            bm25_index: Pre-built BM25 index
            documents: Original documents (same order as index)
            query: Search query text
            top_k: Number of results to return

        Returns:
            Ranked search results
        """
        # Tokenize query
        query_tokens = query.lower().split()

        # Get BM25 scores
        scores = bm25_index.get_scores(query_tokens)

        # Get top-k results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            result = {
                **documents[idx],
                "score": float(scores[idx]),
                "bm25_score": float(scores[idx]),
            }
            results.append(result)

        return results


# Singleton instance
hybrid_search_engine = HybridSearchEngine()
