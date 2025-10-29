"""
Embedder - Generate embeddings for text chunks
"""

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using sentence transformers"""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded, embedding dimension: {self.dimension}")

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Encode texts to embeddings"""
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True  # Normalize for cosine similarity
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise

    def encode_single(self, text: str) -> np.ndarray:
        """Encode single text"""
        return self.encode([text])[0]

    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension"""
        return self.dimension

