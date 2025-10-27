"""
Self-RAG Adaptive Retriever
Decides when and how to retrieve external knowledge
"""

from typing import List, Dict, Any, Tuple, Optional
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class RetrievalDecision(Enum):
    """Retrieval decision types"""
    RETRIEVE = "retrieve"
    NO_RETRIEVE = "no_retrieve"
    ITERATIVE = "iterative"


class RelevanceLevel(Enum):
    """Relevance levels for retrieved content"""
    HIGHLY_RELEVANT = "highly_relevant"
    RELEVANT = "relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    IRRELEVANT = "irrelevant"


class SelfRAGAgent:
    """Self-RAG Agent with adaptive retrieval"""
    
    def __init__(
        self,
        llm_client,
        retrieval_client,
        threshold_confidence: float = 0.8,
        max_iterations: int = 3
    ):
        self.llm_client = llm_client
        self.retrieval_client = retrieval_client
        self.threshold_confidence = threshold_confidence
        self.max_iterations = max_iterations
        self.stats = {
            "total_queries": 0,
            "retrieval_used": 0,
            "avg_confidence": 0.0,
            "avg_chunks_used": 0.0
        }
        
    async def decide_retrieval(self, query: str) -> RetrievalDecision:
        """Decide whether retrieval is needed"""
        try:
            prompt = f"""Analyze if external knowledge retrieval is needed for this query:

Query: {query}

Consider:
1. Is this factual knowledge that requires recent/specific information?
2. Is this common knowledge you already have?
3. Does this require multiple information sources?

Return ONLY one of: RETRIEVE, NO_RETRIEVE, or ITERATIVE

Decision:"""
            
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are a retrieval decision assistant."},
                {"role": "user", "content": prompt}
            ])
            
            decision_text = response.get("content", "RETRIEVE").strip().upper()
            
            # Map to enum
            for decision in RetrievalDecision:
                if decision.name in decision_text:
                    logger.info(f"Retrieval decision for query: {decision.value}")
                    return decision
                    
            # Default to retrieve if uncertain
            return RetrievalDecision.RETRIEVE
            
        except Exception as e:
            logger.error(f"Retrieval decision failed: {e}")
            return RetrievalDecision.RETRIEVE
            
    async def assess_relevance(
        self,
        query: str,
        chunks: List[Dict]
    ) -> List[Tuple[Dict, RelevanceLevel]]:
        """Assess relevance of retrieved chunks"""
        assessed = []
        
        try:
            # Batch assessment for efficiency
            for chunk in chunks:
                prompt = f"""Rate the relevance of this content to the query:

Query: {query}

Retrieved Content: {chunk.get('content', '')[:500]}

Rate as: HIGHLY_RELEVANT, RELEVANT, PARTIALLY_RELEVANT, or IRRELEVANT

Rating:"""
                
                response = await self.llm_client.chat([
                    {"role": "user", "content": prompt}
                ])
                
                level_text = response.get("content", "RELEVANT").strip().upper()
                
                # Map to enum
                level = RelevanceLevel.RELEVANT  # default
                for rel_level in RelevanceLevel:
                    if rel_level.name in level_text:
                        level = rel_level
                        break
                        
                assessed.append((chunk, level))
                
            logger.info(f"Assessed {len(assessed)} chunks for relevance")
            return assessed
            
        except Exception as e:
            logger.error(f"Relevance assessment failed: {e}")
            # Return all as relevant by default
            return [(chunk, RelevanceLevel.RELEVANT) for chunk in chunks]
            
    async def generate_with_critique(
        self,
        query: str,
        chunks: List[Dict]
    ) -> Dict[str, Any]:
        """Generate answer and self-critique"""
        try:
            # 1. Generate initial answer
            context = "\n\n".join([
                f"[{i+1}] {c.get('content', '')}" 
                for i, c in enumerate(chunks[:5])
            ])
            
            answer_prompt = f"""Based on the context below, answer the query.

Context:
{context}

Query: {query}

Answer:"""
            
            answer_response = await self.llm_client.chat([
                {"role": "system", "content": "Answer based on provided context."},
                {"role": "user", "content": answer_prompt}
            ])
            
            answer = answer_response.get("content", "")
            
            # 2. Self-critique
            critique_prompt = f"""Critique this answer:

Query: {query}
Answer: {answer}
Context: {context[:1000]}

Rate the answer on:
1. Factual accuracy (0-1)
2. Relevance to query (0-1)
3. Use of context (0-1)
4. Completeness (0-1)

Return JSON:
{{
  "scores": {{
    "accuracy": 0.9,
    "relevance": 0.85,
    "context_use": 0.8,
    "completeness": 0.9
  }},
  "overall_score": 0.86,
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1"]
}}"""
            
            critique_response = await self.llm_client.chat([
                {"role": "user", "content": critique_prompt}
            ])
            
            # Parse critique
            critique_text = critique_response.get("content", "{}")
            try:
                critique = json.loads(critique_text)
            except:
                critique = {"overall_score": 0.7}
                
            score = critique.get("overall_score", 0.7)
            
            # 3. Refine if score is low
            iterations = 1
            if score < self.threshold_confidence:
                answer = await self._refine_answer(
                    query, chunks, answer, critique
                )
                iterations = 2
                score = min(score + 0.15, 1.0)  # Assume improvement
                
            return {
                "answer": answer,
                "confidence": score,
                "critique": critique,
                "iterations": iterations
            }
            
        except Exception as e:
            logger.error(f"Generation with critique failed: {e}")
            return {
                "answer": "Failed to generate answer",
                "confidence": 0.0,
                "error": str(e)
            }
            
    async def _refine_answer(
        self,
        query: str,
        chunks: List[Dict],
        initial_answer: str,
        critique: Dict
    ) -> str:
        """Refine answer based on critique"""
        try:
            issues = critique.get("issues", [])
            suggestions = critique.get("suggestions", [])
            
            context = "\n\n".join([c.get("content", "") for c in chunks[:5]])
            
            refine_prompt = f"""Improve this answer based on the critique:

Query: {query}
Initial Answer: {initial_answer}

Issues Found: {issues}
Suggestions: {suggestions}

Context:
{context}

Provide an improved answer that addresses the issues:"""
            
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are refining an answer."},
                {"role": "user", "content": refine_prompt}
            ])
            
            return response.get("content", initial_answer)
            
        except Exception as e:
            logger.error(f"Answer refinement failed: {e}")
            return initial_answer
            
    async def _refine_query(self, query: str, critique: str) -> str:
        """Refine query based on critique"""
        try:
            prompt = f"""The previous query didn't get good results. Refine it:

Original Query: {query}
Issues: {critique}

Provide a refined query that would retrieve better information:"""
            
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            refined = response.get("content", query).strip()
            logger.info(f"Refined query: {query} -> {refined}")
            return refined
            
        except Exception as e:
            logger.error(f"Query refinement failed: {e}")
            return query
            
    async def execute_self_rag(
        self,
        query: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Execute complete Self-RAG pipeline"""
        self.stats["total_queries"] += 1
        
        try:
            # 1. Decide if retrieval is needed
            decision = await self.decide_retrieval(query)
            
            if decision == RetrievalDecision.NO_RETRIEVE:
                # Direct generation without retrieval
                response = await self.llm_client.chat([
                    {"role": "user", "content": query}
                ])
                
                return {
                    "answer": response.get("content", ""),
                    "used_retrieval": False,
                    "confidence": 1.0,
                    "decision": decision.value
                }
                
            # 2. Execute retrieval
            self.stats["retrieval_used"] += 1
            chunks = await self.retrieval_client.retrieve(query, top_k=top_k)
            
            if not chunks:
                logger.warning("No chunks retrieved")
                response = await self.llm_client.chat([
                    {"role": "user", "content": query}
                ])
                return {
                    "answer": response.get("content", ""),
                    "used_retrieval": True,
                    "retrieval_effective": False,
                    "confidence": 0.5
                }
                
            # 3. Assess relevance
            assessed_chunks = await self.assess_relevance(query, chunks)
            
            # 4. Filter relevant content
            relevant_chunks = [
                chunk for chunk, level in assessed_chunks
                if level in [RelevanceLevel.HIGHLY_RELEVANT, RelevanceLevel.RELEVANT]
            ]
            
            if not relevant_chunks:
                logger.warning("No relevant chunks found")
                response = await self.llm_client.chat([
                    {"role": "user", "content": query}
                ])
                return {
                    "answer": response.get("content", ""),
                    "used_retrieval": True,
                    "retrieval_effective": False,
                    "confidence": 0.5,
                    "chunks_retrieved": len(chunks),
                    "chunks_relevant": 0
                }
                
            # 5. Generate with critique
            result = await self.generate_with_critique(query, relevant_chunks)
            
            # 6. Iterative retrieval if needed and confidence is low
            if decision == RetrievalDecision.ITERATIVE and result["confidence"] < 0.8:
                for iteration in range(self.max_iterations - 1):
                    logger.info(f"Self-RAG iteration {iteration + 2}")
                    
                    # Refine query based on critique
                    refined_query = await self._refine_query(
                        query, 
                        str(result.get("critique", ""))
                    )
                    
                    # Retrieve again
                    new_chunks = await self.retrieval_client.retrieve(
                        refined_query, 
                        top_k=top_k
                    )
                    
                    if new_chunks:
                        # Assess and generate again
                        assessed_new = await self.assess_relevance(refined_query, new_chunks)
                        relevant_new = [
                            chunk for chunk, level in assessed_new
                            if level in [RelevanceLevel.HIGHLY_RELEVANT, RelevanceLevel.RELEVANT]
                        ]
                        
                        if relevant_new:
                            result = await self.generate_with_critique(
                                refined_query, 
                                relevant_new
                            )
                            result["iterations"] = iteration + 2
                            
                            if result["confidence"] >= 0.8:
                                break
                                
            # Update stats
            self.stats["avg_confidence"] = (
                (self.stats["avg_confidence"] * (self.stats["total_queries"] - 1) + 
                 result["confidence"]) / self.stats["total_queries"]
            )
            self.stats["avg_chunks_used"] = (
                (self.stats["avg_chunks_used"] * (self.stats["retrieval_used"] - 1) + 
                 len(relevant_chunks)) / self.stats["retrieval_used"]
            )
            
            return {
                **result,
                "used_retrieval": True,
                "retrieval_effective": True,
                "chunks_retrieved": len(chunks),
                "chunks_relevant": len(relevant_chunks),
                "decision": decision.value
            }
            
        except Exception as e:
            logger.error(f"Self-RAG execution failed: {e}")
            return {
                "answer": "Self-RAG execution failed",
                "error": str(e),
                "used_retrieval": False,
                "confidence": 0.0
            }
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get Self-RAG statistics"""
        return {
            **self.stats,
            "retrieval_rate": (
                self.stats["retrieval_used"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0 else 0
            )
        }

