from sentence_transformers import SentenceTransformer
from typing import List
from config import Config

class EmbeddingClient:
    def __init__(self):
        self.model = SentenceTransformer(Config.embedding.MODEL_NAME)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return [embedding.tolist() for embedding in embeddings]

    def generate_single_embedding(self, text: str) -> List[float]:
        embedding = self.model.encode([text])[0]
        return embedding.tolist()