from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from models.api_models import QuizConfig
from models.quiz_models import QuizResponse


class GenerationStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class QuizJobMetadata(BaseModel):
    user_id: str
    collection_name: str
    query_text: str
    quiz_config: QuizConfig
    created_at: datetime


class QuizJobStatus(BaseModel):
    quiz_job_id: str
    generation_status: GenerationStatus
    job_metadata: QuizJobMetadata
    quiz_result: Optional[QuizResponse] = None
    quiz_id: Optional[str] = None  # Saved quiz ID in database
    error_message: Optional[str] = None
    progress_percent: int = 0
    updated_at: datetime


class QuizJobResponse(BaseModel):
    quiz_job_id: str
    status: str
    message: str


class QuizStatusResponse(BaseModel):
    quiz_job_id: str
    generation_status: GenerationStatus
    progress_percent: int = 0
    quiz_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class QuizJobListItem(BaseModel):
    quiz_job_id: str
    title: str
    generation_status: GenerationStatus
    collection_name: str
    difficulty: str
    created_at: str