from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

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

class CriticEvaluation(BaseModel):
    confidence: float
    missing_info: str
    enrichment_suggestions: List[str]

class QueryRequest(BaseModel):
    query: str
    enable_critic: bool = True

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

