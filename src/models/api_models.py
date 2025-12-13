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
class LinkContentItem(BaseModel):
    name: str
    file_id: Optional[str] = None
    type: str # 'file', 'youtube', 'web'
    web_url: Optional[str] = None
    youtube_url: Optional[str] = None
    content_type: Optional[ContentType] = ContentType.AUTO  # NEW: Auto-detect by default
    book_metadata: Optional[BookMetadata] = None            # NEW: For book indexing

    @model_validator(mode='before')
    @classmethod
    def check_source_consistency(cls, values):
        if isinstance(values, dict):
            type_val = values.get('type')
            file_id = values.get('file_id')
            web_url = values.get('web_url')
            youtube_url = values.get('youtube_url')
            
            # Skip validation if type is not present (might be partial update? unlikely for this model)
            if not type_val:
                return values

            provided_sources = [v for v in [file_id, web_url, youtube_url] if v is not None]
            if len(provided_sources) != 1:
                raise ValueError("Exactly one of 'file_id', 'web_url', or 'youtube_url' must be provided.")

            if (type_val == 'file' and not file_id) or \
               (type_val == 'web' and not web_url) or \
               (type_val == 'youtube' and not youtube_url):
                raise ValueError(f"Mismatch between type '{type_val}' and provided source URL/ID.")
        return values

class LinkContentResponse(BaseModel):
    name: str
    file_id: str
    type: str
    created_at: Optional[str] = None
    indexing_status: str
    status_code: int
    message: Optional[str] = None

class ChunkConfig(BaseModel):
    source: str
    text: str

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
    query: str
    enable_critic: bool = True
    structured_output: bool = False

class QueryResponse(BaseModel):
    answer: str
    confidence: float
    is_relevant: bool
    chunks: List[ChunkConfig]
    critic: Optional[CriticEvaluation] = None

class FileUploadResponse(BaseModel):
    status: str
    message: str
    body: Dict[str, str]

class UnlinkContentResponse(BaseModel):
    file_id: str
    status_code: int
    message: str

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

