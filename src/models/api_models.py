from pydantic import BaseModel, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class RagConfig(BaseModel):
    name: str
    version: str

class IndexingConfig(BaseModel):
    name: str
    version: str

class CreateCollectionRequest(BaseModel):
    name: str
    rag_config: Optional[RagConfig] = None
    indexing_config: Optional[IndexingConfig] = None

class ApiResponse(BaseModel):
    status: str
    message: str

class ApiResponseWithBody(BaseModel):
    status: str
    message: str
    body: Dict[str, Any]

# Enums - Define before they are used
class ChunkType(str, Enum):
    CONCEPT = "concept"
    EXAMPLE = "example"
    QUESTION = "question"
    OTHER = "other"

class ContentType(str, Enum):
    """Type of content being indexed - determines chunking strategy"""
    BOOK = "book"           # Full textbook (1000+ pages, use larger chunks)
    CHAPTER = "chapter"     # Single chapter (10-50 pages, use medium chunks)
    DOCUMENT = "document"   # Small document (<10 pages, use small chunks)
    AUTO = "auto"           # Auto-detect based on file size

# Metadata models
class BookMetadata(BaseModel):
    """Book-level metadata for full textbook indexing"""
    book_id: Optional[str] = None
    book_title: Optional[str] = None
    book_authors: List[str] = []
    book_edition: Optional[str] = None
    book_subject: Optional[str] = None
    total_chapters: Optional[int] = None
    total_pages: Optional[int] = None

# Chunking configuration
class ChunkingStrategy(BaseModel):
    """Dynamic chunking configuration based on content type"""
    chunk_size: int
    chunk_overlap: int
    content_type: ContentType
    description: str

# Request/Response models
# Request/Response models
# New RAG API Models (per RAG_API_DOC.md)

class IndexingStatus(str, Enum):
    PENDING = "INDEXING_PENDING"
    RUNNING = "INDEXING_RUNNING"
    SUCCESS = "INDEXING_SUCCESS"
    FAILED = "INDEXING_FAILED"

class LinkItem(BaseModel):
    type: str # 'file', 'youtube', 'web'
    file_id: str
    collection_id: Optional[str] = None
    url: Optional[str] = None      # For web/youtube
    gcs_url: Optional[str] = None  # For file

    @model_validator(mode='before')
    @classmethod
    def check_source(cls, values):
        if isinstance(values, dict):
            type_val = values.get('type')
            url = values.get('url')
            gcs_url = values.get('gcs_url')
            
            if type_val in ['youtube', 'web'] and not url:
                raise ValueError(f"{type_val} requires 'url'")
            if type_val == 'file' and not gcs_url:
                raise ValueError("file requires 'gcs_url'")
        return values

class BatchLinkRequest(BaseModel):
    items: List[LinkItem]

class BatchItemResponse(BaseModel):
    file_id: str
    status: str
    error: Optional[str] = None

class IngestionResponse(BaseModel):
    message: str
    batch_id: str
    results: List[BatchItemResponse]

class RetrieveFilters(BaseModel):
    collection_ids: Optional[List[str]] = None
    file_ids: Optional[List[str]] = None

class RetrieveRequest(BaseModel):
    query: str
    filters: Optional[RetrieveFilters] = None
    top_k: int = 5
    include_graph_context: bool = True

class EnrichedChunk(BaseModel):
    chunk_id: str
    chunk_text: str
    relevance_score: float
    file_id: str
    page_number: Optional[int] = None
    timestamp: Optional[str] = None
    concepts: List[str] = []
    # prerequisites: List[str] = [] # Graph feature, can implement if graph is ready, else omit or empty

class RetrieveResponse(BaseModel):
    success: bool
    results: List[EnrichedChunk]

class QueryAnswerRequest(BaseModel):
    query: str
    filters: Optional[RetrieveFilters] = None
    top_k: int = 5
    include_sources: bool = False

class QueryAnswerResponse(BaseModel):
    success: bool
    answer: str
    sources: Optional[List[EnrichedChunk]] = None

class DeleteFileRequest(BaseModel):
    file_ids: List[str]

class DeleteCollectionRequest(BaseModel):
    collection_id: str

class IndexingStatusResponse(BaseModel):
    file_id: str
    status: IndexingStatus
    error: Optional[str] = None

class BatchStatusRequest(BaseModel):
    file_ids: List[str]

class StatusItemResponse(BaseModel):
    file_id: str
    name: Optional[str] = None
    source: Optional[str] = None
    status: str
    error: Optional[str] = None

class BatchStatusResponse(BaseModel):
    message: str
    results: List[StatusItemResponse]






# --- Internal Models for Query Service ---

class ChunkConfig(BaseModel):
    source: str
    text: str
    chunk_id: Optional[str] = None
    relevance_score: Optional[float] = None
    file_id: Optional[str] = None
    page_number: Optional[int] = None
    timestamp: Optional[str] = None
    concepts: List[str] = []

class TopicMetadata(BaseModel):
    chapter_num: Optional[int] = None
    chapter_title: Optional[str] = None
    section_num: Optional[str] = None
    section_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

class ChunkMetadata(BaseModel):
    chunk_type: ChunkType
    topic_id: str
    key_terms: List[str] = []
    equations: List[str] = []
    has_equations: bool = False
    has_diagrams: bool = False
    difficulty_level: Optional[str] = None

class HierarchicalChunk(BaseModel):
    chunk_id: str
    document_id: str
    topic_metadata: TopicMetadata
    chunk_metadata: ChunkMetadata
    text: str
    embedding_vector: Optional[List[float]] = None

class CriticEvaluation(BaseModel):
    confidence: float
    missing_info: str
    enrichment_suggestions: List[str]

class QueryRequest(BaseModel):
    # Legacy wrapper if needed, rag.py uses RetrieveRequest now
    query: str
    enable_critic: bool = True
    structured_output: bool = False

class QueryResponse(BaseModel):
    answer: str
    confidence: float
    is_relevant: bool
    chunks: List[ChunkConfig]
    critic: Optional[CriticEvaluation] = None


class CreateConfigRequest(BaseModel):
    pass

class CreateConfigResponse(BaseModel):
    message: str
    config_id: str

class FeedbackRequest(BaseModel):
    query: str
    doc_ids: List[str]
    label: int
    collection: str

class FeedbackResponse(BaseModel):
    status: str
    message: str

class EmbeddingItem(BaseModel):
    id: str
    document_id: str
    text: str
    source: str
    metadata: Dict[str, Any]
    vector: Optional[List[float]] = None

class GetEmbeddingsResponse(BaseModel):
    status: str
    message: str
    body: Dict[str, Any]

