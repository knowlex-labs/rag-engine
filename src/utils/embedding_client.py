from typing import List
from config import Config
import logging
import os

logger = logging.getLogger(__name__)

class EmbeddingClient:
    _embeddings = None

    def __init__(self):
        if EmbeddingClient._embeddings is None:
            provider = Config.embedding.PROVIDER

            if provider == "openai":
                logger.info("Using OpenAI embeddings: text-embedding-3-large")
                from langchain_openai import OpenAIEmbeddings

                api_key = Config.llm.OPENAI_API_KEY
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment variables")

                EmbeddingClient._embeddings = OpenAIEmbeddings(
                    model="text-embedding-ada-002",
                    openai_api_key=api_key
                )
                logger.info("OpenAI embeddings initialized successfully (1536D)")

            else:
                logger.info(f"Using HuggingFace embeddings: {Config.embedding.MODEL_NAME}")
                from langchain_community.embeddings import HuggingFaceEmbeddings

                cache_dir = os.getenv('HF_HOME', os.path.expanduser('~/.cache/huggingface'))
                os.makedirs(cache_dir, exist_ok=True)

                EmbeddingClient._embeddings = HuggingFaceEmbeddings(
                    model_name=Config.embedding.MODEL_NAME,
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True},
                    cache_folder=cache_dir
                )
                logger.info(f"HuggingFace embeddings loaded successfully ({Config.embedding.VECTOR_SIZE}D)")
        else:
            logger.debug("Using cached embedding model")

    @property
    def embeddings(self):
        return EmbeddingClient._embeddings

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)

    def generate_single_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)


embedding_client = EmbeddingClient()
