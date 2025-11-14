from pydantic import BaseModel
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

class LinkContentItem(BaseModel):
    name: str
    file_id: str
    type: str

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

class ChunkType(str, Enum):
    CONCEPT = "concept"
    EXAMPLE = "example"
    QUESTION = "question"
    OTHER = "other"

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

class QuizConfig(BaseModel):
    template: str = "standard"
    collection_name: str
    num_questions: int
    difficulty: str
    question_types: List[str] = ["multiple_choice"]
    time_limit_minutes: int
    total_score: int
    passing_score: int
    points_per_question: int

class QueryRequest(BaseModel):
    query: str
    enable_critic: bool = True
    structured_output: bool = False
    quiz_config: Optional[QuizConfig] = None

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

