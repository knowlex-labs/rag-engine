from typing import List
from config import Config
import logging
import os

logger = logging.getLogger(__name__)

class EmbeddingClient:
    _client = None

    def __init__(self):
        if EmbeddingClient._client is None:
            provider = Config.embedding.PROVIDER
            
            if provider == "gemini":
                logger.info("Using Gemini embeddings via google-genai")
                from google import genai
                from google.genai import types
                
                api_key = Config.llm.GEMINI_API_KEY
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not found in environment variables")
                
                EmbeddingClient._client = genai.Client(api_key=api_key)
                EmbeddingClient._model_name = "text-embedding-004" # Latest high-performance model
                logger.info("Gemini embedding client initialized")
                
            elif provider == "openai":
                logger.info("Using OpenAI embeddings: text-embedding-ada-002")
                from openai import OpenAI
                api_key = Config.llm.OPENAI_API_KEY
                EmbeddingClient._client = OpenAI(api_key=api_key)
                EmbeddingClient._model_name = "text-embedding-ada-002"
            
            else:
                logger.info(f"Using HuggingFace embeddings: {Config.embedding.MODEL_NAME}")
                from sentence_transformers import SentenceTransformer
                EmbeddingClient._client = SentenceTransformer(Config.embedding.MODEL_NAME)
        
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        provider = Config.embedding.PROVIDER
        
        if provider == "gemini":
            from google.genai import types
            result = EmbeddingClient._client.models.embed_content(
                model=EmbeddingClient._model_name,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=Config.embedding.VECTOR_SIZE)
            )
            return [obj.values for obj in result.embeddings]
            
        elif provider == "openai":
            response = EmbeddingClient._client.embeddings.create(
                input=texts,
                model=EmbeddingClient._model_name
            )
            return [data.embedding for data in response.data]
            
        else:
            return EmbeddingClient._client.encode(texts).tolist()

    def generate_single_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings([text])[0]

embedding_client = EmbeddingClient()
