"""
Advanced Query Rewriting Service with Multiple Strategies
"""

from typing import List, Dict, Any, Optional
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class RewriteStrategy(Enum):
    """Query rewrite strategies"""
    MULTI_QUERY = "multi_query"
    HYDE = "hyde"
    DECOMPOSE = "decompose"
    STEP_BACK = "step_back"
    FUSION = "fusion"
    CONTEXTUAL = "contextual"


class AdvancedQueryRewriter:
    """Advanced query rewriting with multiple strategies"""
    
    def __init__(self, llm_client, embedding_client=None):
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.rewrite_cache = {}
        
    async def rewrite_query(
        self,
        query: str,
        strategy: RewriteStrategy = RewriteStrategy.MULTI_QUERY,
        context: Optional[Dict] = None
    ) -> List[str]:
        """Rewrite query using specified strategy"""
        # Check cache
        cache_key = f"{strategy.value}:{query[:100]}"
        if cache_key in self.rewrite_cache:
            logger.debug(f"Using cached rewrite for: {query[:50]}...")
            return self.rewrite_cache[cache_key]
            
        try:
            if strategy == RewriteStrategy.MULTI_QUERY:
                queries = await self._multi_query(query)
            elif strategy == RewriteStrategy.HYDE:
                queries = await self._hyde(query)
            elif strategy == RewriteStrategy.DECOMPOSE:
                queries = await self._decompose(query)
            elif strategy == RewriteStrategy.STEP_BACK:
                queries = await self._step_back(query)
            elif strategy == RewriteStrategy.FUSION:
                queries = await self._fusion(query)
            elif strategy == RewriteStrategy.CONTEXTUAL:
                queries = await self._contextual(query, context or {})
            else:
                queries = [query]
                
            # Cache result
            self.rewrite_cache[cache_key] = queries
            
            logger.info(f"Rewrote query using {strategy.value}: {len(queries)} variants")
            return queries
            
        except Exception as e:
            logger.error(f"Query rewriting failed: {e}")
            return [query]
            
    async def _multi_query(self, query: str, num_variants: int = 3) -> List[str]:
        """Generate multiple query variants"""
        prompt = f"""Generate {num_variants} different ways to ask the same question. Each variant should use different words but maintain the same intent.

Original Question: {query}

Generate {num_variants} variants (one per line, numbered):"""
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a query reformulation expert."},
            {"role": "user", "content": prompt}
        ])
        
        variants_text = response.get("content", "")
        
        # Parse variants
        variants = [query]  # Always include original
        for line in variants_text.split('\n'):
            line = line.strip()
            if line:
                # Remove numbering
                cleaned = line.lstrip('0123456789.-) ')
                if cleaned and cleaned != query:
                    variants.append(cleaned)
                    
        return variants[:num_variants + 1]
        
    async def _hyde(self, query: str) -> List[str]:
        """HyDE: Generate hypothetical document embedding"""
        prompt = f"""Generate a detailed hypothetical document/passage that would perfectly answer this question:

Question: {query}

Write a comprehensive passage (2-3 paragraphs) that contains the answer:"""
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are writing a hypothetical answer passage."},
            {"role": "user", "content": prompt}
        ])
        
        hypothetical_doc = response.get("content", "").strip()
        
        # Return both original query and hypothetical document
        return [query, hypothetical_doc]
        
    async def _decompose(self, query: str) -> List[str]:
        """Decompose complex query into sub-questions"""
        prompt = f"""Break down this complex question into 2-4 simpler sub-questions that, when answered together, would address the main question.

Main Question: {query}

List sub-questions (one per line):"""
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a question decomposition expert."},
            {"role": "user", "content": prompt}
        ])
        
        sub_questions_text = response.get("content", "")
        
        # Parse sub-questions
        sub_questions = [query]  # Include original
        for line in sub_questions_text.split('\n'):
            line = line.strip()
            if line:
                cleaned = line.lstrip('0123456789.-) ')
                if cleaned and cleaned != query:
                    sub_questions.append(cleaned)
                    
        return sub_questions
        
    async def _step_back(self, query: str) -> List[str]:
        """Step-back prompting: Generate broader context question"""
        prompt = f"""Given this specific question, generate a more general/broader question that would help establish context for answering the specific question.

Specific Question: {query}

Generate ONE broader question:"""
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a context expansion expert."},
            {"role": "user", "content": prompt}
        ])
        
        broader_question = response.get("content", "").strip()
        
        # Return both specific and broader questions
        return [query, broader_question]
        
    async def _fusion(self, query: str) -> List[str]:
        """RAG Fusion: Combine multiple strategies"""
        # Run multiple strategies in parallel
        results = await asyncio.gather(
            self._multi_query(query, 2),
            self._step_back(query),
            return_exceptions=True
        )
        
        # Combine all queries
        all_queries = [query]
        for result in results:
            if isinstance(result, list):
                all_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Fusion sub-strategy failed: {result}")
                
        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in all_queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)
                
        return unique_queries
        
    async def _contextual(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Contextual rewriting using conversation history"""
        conversation_history = context.get("conversation_history", [])
        user_profile = context.get("user_profile", {})
        
        # Build context string
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 turns
            history_text = "\n".join([
                f"{turn['role']}: {turn['content']}"
                for turn in recent_history
            ])
            
        profile_text = ""
        if user_profile:
            profile_text = f"User: {user_profile.get('name', 'Unknown')}, Interests: {user_profile.get('interests', [])}"
            
        prompt = f"""Rewrite this query considering the conversation context and user profile:

Conversation History:
{history_text}

{profile_text}

Current Query: {query}

Generate 2-3 context-aware reformulations:"""
        
        response = await self.llm_client.chat([
            {"role": "system", "content": "You are a context-aware query reformulation expert."},
            {"role": "user", "content": prompt}
        ])
        
        reformulations_text = response.get("content", "")
        
        # Parse reformulations
        reformulations = [query]
        for line in reformulations_text.split('\n'):
            line = line.strip()
            if line:
                cleaned = line.lstrip('0123456789.-) ')
                if cleaned and cleaned != query:
                    reformulations.append(cleaned)
                    
        return reformulations
        
    async def auto_select_strategy(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> RewriteStrategy:
        """Automatically select best rewriting strategy"""
        # Analyze query characteristics
        word_count = len(query.split())
        has_context = context and context.get("conversation_history")
        
        # Simple heuristics for strategy selection
        if has_context:
            return RewriteStrategy.CONTEXTUAL
        elif word_count > 15:  # Complex query
            return RewriteStrategy.DECOMPOSE
        elif "how" in query.lower() or "why" in query.lower():
            return RewriteStrategy.STEP_BACK
        else:
            return RewriteStrategy.MULTI_QUERY
            
    async def rewrite_with_auto_strategy(
        self,
        query: str,
        context: Optional[Dict] = None
    ) -> List[str]:
        """Rewrite query with automatically selected strategy"""
        strategy = await self.auto_select_strategy(query, context)
        logger.info(f"Auto-selected strategy: {strategy.value}")
        return await self.rewrite_query(query, strategy, context)
        
    def clear_cache(self):
        """Clear rewrite cache"""
        self.rewrite_cache.clear()
        logger.info("Query rewrite cache cleared")
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get rewriting statistics"""
        return {
            "cache_size": len(self.rewrite_cache),
            "strategies_available": [s.value for s in RewriteStrategy]
        }


class QueryExpander:
    """Query expansion using synonyms and related terms"""
    
    def __init__(self, embedding_client=None):
        self.embedding_client = embedding_client
        
    async def expand_query(
        self,
        query: str,
        max_expansions: int = 5
    ) -> List[str]:
        """Expand query with synonyms and related terms"""
        # Simple keyword-based expansion
        # In production, use WordNet, word embeddings, or LLM
        expansions = [query]
        
        # Common term mappings
        term_mappings = {
            "buy": ["purchase", "acquire", "get"],
            "问题": ["trouble", "issue", "problem"],
            "帮助": ["help", "assist", "support"],
            "如何": ["how to", "ways to", "methods"],
        }
        
        query_lower = query.lower()
        for term, synonyms in term_mappings.items():
            if term in query_lower:
                for synonym in synonyms[:max_expansions]:
                    expanded = query_lower.replace(term, synonym)
                    if expanded != query_lower:
                        expansions.append(expanded)
                        
        return expansions[:max_expansions + 1]
        
    async def expand_with_embeddings(
        self,
        query: str,
        corpus: List[str],
        top_k: int = 5
    ) -> List[str]:
        """Expand query using embedding similarity"""
        if not self.embedding_client:
            return [query]
            
        try:
            # Get query embedding
            query_embedding = await self.embedding_client.embed(query)
            
            # Get corpus embeddings
            corpus_embeddings = await self.embedding_client.embed_batch(corpus)
            
            # Calculate similarities
            import numpy as np
            similarities = []
            for i, corpus_emb in enumerate(corpus_embeddings):
                sim = np.dot(query_embedding, corpus_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(corpus_emb)
                )
                similarities.append((sim, corpus[i]))
                
            # Sort by similarity
            similarities.sort(reverse=True, key=lambda x: x[0])
            
            # Return top-k similar queries
            expansions = [query]
            expansions.extend([q for _, q in similarities[:top_k]])
            
            return expansions
            
        except Exception as e:
            logger.error(f"Embedding-based expansion failed: {e}")
            return [query]

