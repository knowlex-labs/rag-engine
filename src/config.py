import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DatabaseConfig:
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_TIMEOUT: int = int(os.getenv("QDRANT_TIMEOUT", "30"))
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

class EmbeddingConfig:
    MODEL_NAME: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    VECTOR_SIZE: int = int(os.getenv("VECTOR_SIZE", "1024"))
    DISTANCE_METRIC: str = os.getenv("DISTANCE_METRIC", "COSINE")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

class LlmConfig:
    PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "4000"))
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))

class AppConfig:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", "uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

class RerankingConfig:
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "5"))
    RERANKER_ENABLED: bool = os.getenv("RERANKER_ENABLED", "true").lower() == "true"

class CriticConfig:
    CRITIC_ENABLED: bool = os.getenv("CRITIC_ENABLED", "true").lower() == "true"
    CRITIC_MODEL_NAME: str = os.getenv("CRITIC_MODEL_NAME", "models/gemini-2.5-flash")
    CRITIC_MODEL_API_KEY: str = os.getenv("CRITIC_MODEL_API_KEY", "")
    CRITIC_MODEL_TEMPERATURE: float = float(os.getenv("CRITIC_MODEL_TEMPERATURE", "0.1"))

class FeedbackConfig:
    FEEDBACK_ENABLED: bool = os.getenv("FEEDBACK_ENABLED", "true").lower() == "true"
    FEEDBACK_SIMILARITY_THRESHOLD: float = float(os.getenv("FEEDBACK_SIMILARITY_THRESHOLD", "0.8"))

class Config:
    database = DatabaseConfig()
    embedding = EmbeddingConfig()
    llm = LlmConfig()
    app = AppConfig()
    reranking = RerankingConfig()
    critic = CriticConfig()
    feedback = FeedbackConfig()