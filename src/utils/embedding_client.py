from sentence_transformers import SentenceTransformer
from typing import List
from config import Config
import logging

logger = logging.getLogger(__name__)

class EmbeddingClient:
    _model = None

    def __init__(self):
        if EmbeddingClient._model is None:
            logger.info(f"Loading embedding model: {Config.embedding.MODEL_NAME}")
            EmbeddingClient._model = SentenceTransformer(Config.embedding.MODEL_NAME)
            logger.info("Embedding model loaded successfully!")
        else:
            logger.debug("Using cached embedding model")

    @property
    def model(self):
        return EmbeddingClient._model

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return [embedding.tolist() for embedding in embeddings]

    def generate_single_embedding(self, text: str) -> List[float]:
        embedding = self.model.encode([text])[0]
        return embedding.tolist()


# Create a global instance for reuse
embedding_client = EmbeddingClient()