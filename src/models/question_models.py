"""
Pydantic models for the UGC NET Question Generation API
"""

from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator


class QuestionType(str, Enum):
    """Supported question types for UGC NET exam"""
    ASSERTION_REASONING = "assertion_reasoning"
    MATCH_FOLLOWING = "match_following"
    COMPREHENSION = "comprehension"


class DifficultyLevel(str, Enum):
    """Difficulty levels aligned with UGC NET exam pattern"""
    EASY = "easy"
    MODERATE = "moderate"
    DIFFICULT = "difficult"


class ExamType(str, Enum):
    """Supported exam types"""
    UGC_NET = "ugc_net"
    GENERAL = "general"


class QuestionFilters(BaseModel):
    """Filters for smart content selection using Neo4j graph"""
    collection_ids: Optional[List[str]] = Field(None, description="Filter by specific collections")
    file_ids: Optional[List[str]] = Field(None, description="Filter by specific files")
    entities: Optional[List[str]] = Field(None, description="Filter by legal entities (e.g., 'Supreme Court', 'Constitutional Law')")
    relationships: Optional[List[str]] = Field(None, description="Filter by relationship types (e.g., 'CONTRADICTS', 'SUPPORTS', 'DEFINES')")
    chunk_types: Optional[List[str]] = Field(None, description="Filter by chunk types (e.g., 'concept', 'example')")
    chapters: Optional[List[str]] = Field(None, description="Filter by chapter titles")
    key_terms: Optional[List[str]] = Field(None, description="Filter by key terms")
    min_text_length: Optional[int] = Field(200, description="Minimum text length for content selection")
    exclude_file_ids: Optional[List[str]] = Field(None, description="Exclude specific files")


class QuestionRequest(BaseModel):
    """Individual question generation request"""
    type: QuestionType = Field(..., description="Type of question to generate")
    count: int = Field(1, ge=1, le=10, description="Number of questions to generate (1-10)")
    difficulty: DifficultyLevel = Field(DifficultyLevel.MODERATE, description="Difficulty level")
    filters: Optional[QuestionFilters] = Field(None, description="Content selection filters")


class GenerationContext(BaseModel):
    """Context for question generation"""
    exam_type: ExamType = Field(ExamType.UGC_NET, description="Type of exam")
    subject: Optional[str] = Field("law", description="Subject area (e.g., 'law', 'political_science')")
    avoid_duplicates: bool = Field(True, description="Avoid generating duplicate questions")
    include_explanations: bool = Field(True, description="Include detailed explanations")
    language: str = Field("english", description="Language for questions")


class QuestionGenerationRequest(BaseModel):
    """Main request model for question generation API"""
    questions: List[QuestionRequest] = Field(..., min_items=1, max_items=5, description="List of question generation requests")
    context: Optional[GenerationContext] = Field(default_factory=GenerationContext, description="Generation context")

    @validator('questions')
    def validate_total_questions(cls, v):
        total = sum(q.count for q in v)
        if total > 20:
            raise ValueError("Total questions cannot exceed 20 per request")
        return v


# Response Models

class AssertionReasonQuestion(BaseModel):
    """Assertion-Reasoning question format"""
    question_text: str = Field(..., description="Question instructions")
    assertion: str = Field(..., description="Assertion (A) statement")
    reason: str = Field(..., description="Reason (R) statement")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Four standard options")
    correct_option: str = Field(..., description="Correct answer option")
    explanation: str = Field(..., description="Detailed explanation of the answer")
    difficulty: DifficultyLevel = Field(..., description="Actual difficulty level")
    source_chunks: List[str] = Field(default_factory=list, description="Source chunk IDs used")


class MatchFollowingQuestion(BaseModel):
    """Match the Following question format"""
    question_text: str = Field(..., description="Question instructions")
    list_I: List[str] = Field(..., min_items=4, max_items=4, description="List I items")
    list_II: List[str] = Field(..., min_items=4, max_items=4, description="List II items")
    correct_matches: Dict[str, str] = Field(..., description="Correct matches mapping")
    explanation: str = Field(..., description="Explanation of correct matches")
    difficulty: DifficultyLevel = Field(..., description="Actual difficulty level")
    source_chunks: List[str] = Field(default_factory=list, description="Source chunk IDs used")


class ComprehensionQuestion(BaseModel):
    """Comprehension-based question format"""
    passage: str = Field(..., description="Reading passage")
    questions: List[Dict[str, Any]] = Field(..., min_items=2, max_items=5, description="Multiple questions based on passage")
    difficulty: DifficultyLevel = Field(..., description="Actual difficulty level")
    source_chunks: List[str] = Field(default_factory=list, description="Source chunk IDs used")


class QuestionMetadata(BaseModel):
    """Metadata for generated questions"""
    question_id: str = Field(..., description="Unique question identifier")
    type: QuestionType = Field(..., description="Question type")
    difficulty: DifficultyLevel = Field(..., description="Difficulty level")
    estimated_time: int = Field(..., description="Estimated time to solve in minutes")
    source_entities: List[str] = Field(default_factory=list, description="Related legal entities")
    source_files: List[str] = Field(default_factory=list, description="Source file IDs")
    generated_at: str = Field(..., description="Generation timestamp")
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="Quality assessment score")


class GeneratedQuestion(BaseModel):
    """Unified question response model"""
    metadata: QuestionMetadata = Field(..., description="Question metadata")
    content: Union[AssertionReasonQuestion, MatchFollowingQuestion, ComprehensionQuestion] = Field(..., description="Question content")


class QuestionGenerationResponse(BaseModel):
    """Response model for question generation API"""
    success: bool = Field(..., description="Generation success status")
    total_generated: int = Field(..., description="Total number of questions generated")
    questions: List[GeneratedQuestion] = Field(..., description="Generated questions")
    generation_stats: Dict[str, Any] = Field(default_factory=dict, description="Generation statistics")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Any warnings")


class QuestionGenerationError(BaseModel):
    """Error response model"""
    success: bool = Field(False, description="Always false for error responses")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# Content Selection Models

class ContentChunk(BaseModel):
    """Content chunk for question generation"""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    file_id: str = Field(..., description="Source file ID")
    collection_id: str = Field(..., description="Collection ID")
    chunk_type: str = Field(..., description="Chunk type (concept, example, etc.)")
    key_terms: List[str] = Field(default_factory=list, description="Key terms in chunk")
    entities: List[str] = Field(default_factory=list, description="Related entities")
    difficulty_score: Optional[float] = Field(None, description="Computed difficulty score")
    chapter_title: Optional[str] = Field(None, description="Chapter title")
    section_title: Optional[str] = Field(None, description="Section title")


class EntityRelationship(BaseModel):
    """Entity relationship for graph-based selection"""
    source_entity: str = Field(..., description="Source entity")
    target_entity: str = Field(..., description="Target entity")
    relationship_type: str = Field(..., description="Relationship type")
    context: Optional[str] = Field(None, description="Relationship context")


class ContentSelectionResult(BaseModel):
    """Result of content selection process"""
    selected_chunks: List[ContentChunk] = Field(..., description="Selected content chunks")
    entity_relationships: List[EntityRelationship] = Field(default_factory=list, description="Relevant entity relationships")
    selection_strategy: str = Field(..., description="Strategy used for selection")
    coverage_score: Optional[float] = Field(None, description="Content coverage score")