"""
Pydantic models for the Indian Law Query API
Supports constitutional questions, BNS queries, and future legal document integration.
"""

from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator


class LegalDocumentType(str, Enum):
    """Supported legal document types"""
    CONSTITUTION = "constitution"
    BNS = "bns"  # Bharatiya Nyaya Sanhita
    IPC = "ipc"  # Indian Penal Code (legacy)
    CPC = "cpc"  # Code of Civil Procedure
    CRPC = "crpc"  # Code of Criminal Procedure
    ALL = "all"


class AnswerStyle(str, Enum):
    """Answer formatting styles for different audiences"""
    BRIEF = "brief"  # Concise, bullet-point style
    DETAILED = "detailed"  # Comprehensive explanation
    STUDENT_FRIENDLY = "student_friendly"  # Educational with examples
    PROFESSIONAL = "professional"  # Legal practitioner focused
    EXAM_PREP = "exam_prep"  # CLAT/UGC NET optimized


class LegalSourceReference(BaseModel):
    """Reference to specific legal provision"""
    document_type: LegalDocumentType = Field(..., description="Type of legal document")
    article_number: Optional[str] = Field(None, description="Article/Section number (e.g., 'Art-21', 'Sec-302')")
    title: str = Field(..., description="Title or heading of the provision")
    part_chapter: Optional[str] = Field(None, description="Part/Chapter reference (e.g., 'Part III')")
    text_excerpt: str = Field(..., description="Relevant text excerpt from the provision")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score to the query")
    page_reference: Optional[str] = Field(None, description="Page or location reference")


class LegalConcept(BaseModel):
    """Legal concept extracted from the query/answer"""
    name: str = Field(..., description="Name of the legal concept")
    category: str = Field(..., description="Category (e.g., 'Fundamental Right', 'Constitutional Principle')")
    definition: Optional[str] = Field(None, description="Brief definition")
    related_articles: List[str] = Field(default=[], description="Related article/section numbers")


class ConfidenceMetrics(BaseModel):
    """Confidence and quality metrics for the answer"""
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in the answer")
    source_reliability: float = Field(..., ge=0.0, le=1.0, description="Reliability of sources used")
    answer_completeness: float = Field(..., ge=0.0, le=1.0, description="Completeness of the answer")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance of retrieved context")


class LawQueryRequest(BaseModel):
    """Request model for legal question querying"""
    question: str = Field(..., min_length=10, max_length=1000, description="Legal question to be answered")

    # Document scope
    scope: List[LegalDocumentType] = Field(
        default=[LegalDocumentType.CONSTITUTION],
        description="Legal documents to search in"
    )

    # Answer customization
    answer_style: AnswerStyle = Field(
        default=AnswerStyle.STUDENT_FRIENDLY,
        description="Style of answer formatting"
    )
    max_answer_length: Optional[int] = Field(
        default=500,
        ge=100,
        le=2000,
        description="Maximum words in answer"
    )

    # Context and sources
    include_sources: bool = Field(default=True, description="Include source references")
    max_sources: int = Field(default=5, ge=1, le=10, description="Maximum number of source references")
    max_context_chunks: int = Field(default=5, ge=1, le=15, description="Maximum context chunks to retrieve")

    # Advanced options
    include_related_concepts: bool = Field(default=True, description="Include related legal concepts")
    include_confidence_metrics: bool = Field(default=False, description="Include confidence scoring")
    highlight_key_terms: bool = Field(default=True, description="Highlight key legal terms in answer")

    # Filtering options
    specific_articles: Optional[List[str]] = Field(None, description="Focus on specific articles (e.g., ['Art-21', 'Art-14'])")
    exclude_articles: Optional[List[str]] = Field(None, description="Exclude specific articles")
    topic_focus: Optional[str] = Field(None, description="Focus on specific topic (e.g., 'fundamental rights')")

    @validator('scope')
    def validate_scope(cls, v):
        if not v:
            raise ValueError("At least one document scope must be specified")
        return v

    @validator('question')
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class LawQueryResponse(BaseModel):
    """Response model for legal question answers"""
    # Core answer
    answer: str = Field(..., description="Generated answer to the legal question")
    question: str = Field(..., description="Original question asked")

    # Sources and references
    sources: List[LegalSourceReference] = Field(default=[], description="Legal source references")

    # Related information
    related_concepts: List[LegalConcept] = Field(default=[], description="Related legal concepts")
    related_questions: List[str] = Field(default=[], description="Suggested related questions")

    # Metadata
    answer_style: AnswerStyle = Field(..., description="Style used for answer formatting")
    documents_searched: List[LegalDocumentType] = Field(..., description="Documents that were searched")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")

    # Optional metrics
    confidence_metrics: Optional[ConfidenceMetrics] = Field(None, description="Confidence and quality metrics")

    # Context information
    total_chunks_found: int = Field(..., description="Total context chunks found")
    chunks_used: int = Field(..., description="Number of chunks actually used")

    class Config:
        json_encoders = {
            # Custom encoders if needed
        }


class LawQueryError(BaseModel):
    """Error response for legal query failures"""
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestions: List[str] = Field(default=[], description="Suggestions to fix the query")


# Batch query models for efficiency
class BatchLawQueryRequest(BaseModel):
    """Request model for batch legal queries"""
    queries: List[LawQueryRequest] = Field(..., max_items=10, description="List of legal queries (max 10)")
    parallel_processing: bool = Field(default=True, description="Process queries in parallel")


class BatchLawQueryResponse(BaseModel):
    """Response model for batch legal queries"""
    results: List[Union[LawQueryResponse, LawQueryError]] = Field(..., description="Results for each query")
    total_queries: int = Field(..., description="Total number of queries processed")
    successful_queries: int = Field(..., description="Number of successful queries")
    failed_queries: int = Field(..., description="Number of failed queries")
    total_processing_time_ms: int = Field(..., description="Total processing time in milliseconds")