from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QuizSource(BaseModel):
    type: str = "collection"
    collection_name: str
    source_count: int

class QuizMetadata(BaseModel):
    quiz_id: str
    title: str
    difficulty: str
    estimated_time_minutes: int
    total_questions: int
    max_score: int
    created_at: str
    source: QuizSource

class QuestionConfig(BaseModel):
    question_text: str
    type: str = "multiple_choice"
    difficulty: str
    topic: str
    requires_diagram: bool = False
    contains_math: bool = False
    diagram_type: Optional[str] = None

class AnswerConfig(BaseModel):
    options: Dict[str, str]  # {"A": "option text", "B": "option text", ...}
    correct_answer: str
    max_score: int
    partial_credit: bool = False

class QuestionContext(BaseModel):
    explanation: str
    source_reference: str
    learning_objective: str

class QuizQuestion(BaseModel):
    question_id: str
    question_config: QuestionConfig
    answer_config: AnswerConfig
    context: QuestionContext

class ContentSummary(BaseModel):
    main_summary: str
    key_concepts: List[str]
    topics_covered: List[str]
    prerequisite_knowledge: List[str]

class ScoringInfo(BaseModel):
    total_score: int
    passing_score: int
    time_limit_minutes: int

class QuizData(BaseModel):
    quiz_metadata: QuizMetadata
    questions: List[QuizQuestion]
    content_summary: ContentSummary
    scoring_info: ScoringInfo

class ContentSource(BaseModel):
    source_id: str
    content_preview: str
    relevance_score: float

class GenerationMetadata(BaseModel):
    confidence: float
    is_relevant: bool
    generation_time_ms: int
    model_used: str
    content_sources: List[ContentSource]

class QuizResponse(BaseModel):
    quiz_data: QuizData
    generation_metadata: GenerationMetadata


# Quiz Submission Models
class QuizSubmissionRequest(BaseModel):
    answers: Dict[str, str]  # {"forces_q1": "B", "friction_q3": "A"}
    time_taken_seconds: int
    submitted_at: str


class AnswerResult(BaseModel):
    question_id: str
    submitted_answer: str
    correct_answer: str
    is_correct: bool
    points_earned: int
    max_points: int
    question_text: str


class QuizSubmissionResponse(BaseModel):
    quiz_job_id: str
    total_score: int
    max_score: int
    percentage: float
    passed: bool
    time_taken_seconds: int
    submitted_at: str
    answer_results: List[AnswerResult]
    summary: Dict[str, int]  # {"correct": 5, "incorrect": 2, "total": 7}