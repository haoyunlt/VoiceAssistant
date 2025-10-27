"""
Self-Critique Generation for Self-RAG
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CritiqueScore:
    """Critique scores for different aspects"""
    accuracy: float
    relevance: float
    context_use: float
    completeness: float
    overall: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "accuracy": self.accuracy,
            "relevance": self.relevance,
            "context_use": self.context_use,
            "completeness": self.completeness,
            "overall": self.overall
        }


class CritiqueGenerator:
    """Generates critiques for generated answers"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        
    async def generate_critique(
        self,
        query: str,
        answer: str,
        context: str,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive critique"""
        try:
            # Build critique prompt
            prompt = self._build_critique_prompt(
                query, answer, context, reference
            )
            
            # Get critique from LLM
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are an expert answer critic."},
                {"role": "user", "content": prompt}
            ])
            
            critique_text = response.get("content", "")
            
            # Parse critique
            critique = self._parse_critique(critique_text)
            
            return critique
            
        except Exception as e:
            logger.error(f"Critique generation failed: {e}")
            return {
                "scores": CritiqueScore(0.5, 0.5, 0.5, 0.5, 0.5).to_dict(),
                "issues": ["Failed to generate critique"],
                "suggestions": [],
                "error": str(e)
            }
            
    def _build_critique_prompt(
        self,
        query: str,
        answer: str,
        context: str,
        reference: Optional[str] = None
    ) -> str:
        """Build critique prompt"""
        prompt = f"""Critically evaluate this answer:

Query: {query}

Answer: {answer}

Context Used:
{context[:1500]}

Evaluate on these criteria (score 0.0 to 1.0 for each):

1. **Factual Accuracy**: Are all facts correct? No hallucinations?
2. **Relevance**: Does the answer address the query?
3. **Context Use**: Is the provided context properly used?
4. **Completeness**: Is the answer complete and thorough?

"""
        
        if reference:
            prompt += f"\nReference Answer (for comparison):\n{reference}\n"
            
        prompt += """
Return your critique in this JSON format:
{
  "scores": {
    "accuracy": 0.9,
    "relevance": 0.85,
    "context_use": 0.8,
    "completeness": 0.9
  },
  "overall_score": 0.86,
  "issues": [
    "Issue 1 description",
    "Issue 2 description"
  ],
  "suggestions": [
    "Suggestion 1 for improvement",
    "Suggestion 2 for improvement"
  ],
  "strengths": [
    "Strength 1",
    "Strength 2"
  ]
}"""
        
        return prompt
        
    def _parse_critique(self, critique_text: str) -> Dict[str, Any]:
        """Parse critique response"""
        import json
        import re
        
        try:
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', critique_text, re.DOTALL)
            if json_match:
                critique = json.loads(json_match.group())
            else:
                # Fallback parsing
                critique = {"scores": {}, "issues": [], "suggestions": []}
                
            # Calculate overall score if not present
            if "overall_score" not in critique:
                scores = critique.get("scores", {})
                if scores:
                    overall = sum(scores.values()) / len(scores)
                    critique["overall_score"] = overall
                else:
                    critique["overall_score"] = 0.5
                    
            # Ensure all required fields
            critique.setdefault("issues", [])
            critique.setdefault("suggestions", [])
            critique.setdefault("strengths", [])
            
            return critique
            
        except Exception as e:
            logger.error(f"Critique parsing failed: {e}")
            return {
                "scores": {
                    "accuracy": 0.5,
                    "relevance": 0.5,
                    "context_use": 0.5,
                    "completeness": 0.5
                },
                "overall_score": 0.5,
                "issues": ["Failed to parse critique"],
                "suggestions": [],
                "strengths": []
            }
            
    async def critique_with_comparison(
        self,
        query: str,
        candidate_answers: List[str],
        context: str
    ) -> Dict[str, Any]:
        """Compare and critique multiple answers"""
        try:
            critiques = []
            
            # Critique each answer
            for i, answer in enumerate(candidate_answers):
                critique = await self.generate_critique(
                    query, answer, context
                )
                critique["answer_id"] = i
                critique["answer"] = answer
                critiques.append(critique)
                
            # Rank answers
            ranked = sorted(
                critiques,
                key=lambda c: c.get("overall_score", 0),
                reverse=True
            )
            
            return {
                "critiques": critiques,
                "ranked_answers": ranked,
                "best_answer": ranked[0] if ranked else None
            }
            
        except Exception as e:
            logger.error(f"Comparative critique failed: {e}")
            return {"error": str(e)}
            
    async def generate_improvement_suggestions(
        self,
        query: str,
        answer: str,
        critique: Dict[str, Any]
    ) -> List[str]:
        """Generate specific improvement suggestions"""
        try:
            issues = critique.get("issues", [])
            scores = critique.get("scores", {})
            
            # Identify weak areas
            weak_areas = [
                area for area, score in scores.items()
                if score < 0.7
            ]
            
            prompt = f"""Given this answer and its issues, provide specific actionable improvements:

Query: {query}
Answer: {answer}

Issues Identified:
{chr(10).join(f'- {issue}' for issue in issues)}

Weak Areas: {', '.join(weak_areas)}

Provide 3-5 specific, actionable suggestions to improve this answer:
1. 
2.
3.
"""
            
            response = await self.llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            suggestions_text = response.get("content", "")
            
            # Parse suggestions
            suggestions = []
            for line in suggestions_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering
                    suggestion = line.lstrip('0123456789.-) ')
                    if suggestion:
                        suggestions.append(suggestion)
                        
            return suggestions
            
        except Exception as e:
            logger.error(f"Improvement suggestion generation failed: {e}")
            return ["Unable to generate suggestions"]
            
    async def detect_hallucinations(
        self,
        answer: str,
        context: str
    ) -> Dict[str, Any]:
        """Detect potential hallucinations in answer"""
        try:
            prompt = f"""Detect any hallucinations or unsupported claims in this answer:

Answer: {answer}

Available Context:
{context}

For each claim in the answer, check if it's supported by the context.

Return JSON:
{{
  "hallucinations": [
    {{
      "claim": "specific claim text",
      "supported": false,
      "reason": "why it's a hallucination"
    }}
  ],
  "hallucination_score": 0.2,
  "is_trustworthy": true
}}"""
            
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are a fact-checker."},
                {"role": "user", "content": prompt}
            ])
            
            import json
            import re
            
            result_text = response.get("content", "{}")
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {
                    "hallucinations": [],
                    "hallucination_score": 0.0,
                    "is_trustworthy": True
                }
                
            return result
            
        except Exception as e:
            logger.error(f"Hallucination detection failed: {e}")
            return {
                "hallucinations": [],
                "hallucination_score": 0.0,
                "is_trustworthy": True,
                "error": str(e)
            }

