"""
Pydantic models for Legal Question Generation API
Enhanced for CLAT, UGC NET, and Judiciary exam patterns with constitutional focus.
"""

from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator


class ExamType(str, Enum):
    """Supported legal exam types under LAW domain"""
    CLAT = "clat"  # Common Law Admission Test
    UGC_NET = "ugc_net"  # UGC NET Law
    JUDICIARY = "judiciary"  # Judicial Services Exams
    UPSC = "upsc"  # UPSC Law Optional
    AILET = "ailet"  # All India Law Entrance Test
    LAW = "law"  # General LAW domain questions


class LegalQuestionType(str, Enum):
    """Legal exam question types"""
    MULTIPLE_CHOICE = "multiple_choice"
    ASSERTION_REASONING = "assertion_reasoning"
    MATCH_FOLLOWING = "match_following"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    CASE_BASED = "case_based"
    LEGAL_REASONING = "legal_reasoning"
    FACTUAL_KNOWLEDGE = "factual_knowledge"


class DifficultyLevel(str, Enum):
    """Question difficulty levels aligned with legal exams"""
    EASY = "easy"  # Basic factual knowledge
    MEDIUM = "medium"  # Application and understanding
    HARD = "hard"  # Analysis and critical thinking
    EXPERT = "expert"  # Advanced legal reasoning


class ConstitutionalTopic(str, Enum):
    """Constitutional law topics for focused question generation"""
    FUNDAMENTAL_RIGHTS = "fundamental_rights"
    DIRECTIVE_PRINCIPLES = "directive_principles"
    EMERGENCY_PROVISIONS = "emergency_provisions"
    FEDERALISM = "federalism"
    PARLIAMENT = "parliament"
    EXECUTIVE = "executive"
    JUDICIARY = "judiciary"
    CONSTITUTIONAL_AMENDMENTS = "constitutional_amendments"
    CITIZENSHIP = "citizenship"
    ELECTION_COMMISSION = "election_commission"
    COMPTROLLER_AUDITOR_GENERAL = "comptroller_auditor_general"
    PUBLIC_SERVICE_COMMISSIONS = "public_service_commissions"


class LegalQuestionFilters(BaseModel):
    """Advanced filters for legal question generation"""
    constitutional_topics: Optional[List[ConstitutionalTopic]] = Field(
        None, description="Focus on specific constitutional topics"
    )
    specific_articles: Optional[List[str]] = Field(
        None, description="Generate questions on specific articles (e.g., ['Art-21', 'Art-14'])"
    )
    parts: Optional[List[str]] = Field(
        None, description="Focus on specific constitutional parts (e.g., ['Part III', 'Part IV'])"
    )
    landmark_cases: bool = Field(
        False, description="Include landmark case-based questions"
    )
    amendments: bool = Field(
        False, description="Include constitutional amendment-based questions"
    )
    comparative_analysis: bool = Field(
        False, description="Generate questions requiring comparison between provisions"
    )
    exclude_topics: Optional[List[ConstitutionalTopic]] = Field(
        None, description="Topics to exclude from question generation"
    )
    year_range: Optional[tuple[int, int]] = Field(
        None, description="Focus on amendments/cases within year range"
    )


class MultipleChoiceQuestion(BaseModel):
    """Multiple choice question structure"""
    question: str = Field(..., description="The question statement")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Four answer options")
    correct_answer: str = Field(..., description="Correct answer (A/B/C/D)")
    explanation: str = Field(..., description="Detailed explanation with constitutional references")


class AssertionReasoningQuestion(BaseModel):
    """Assertion-reasoning question structure popular in CLAT"""
    assertion: str = Field(..., description="The assertion statement")
    reasoning: str = Field(..., description="The reasoning statement")
    options: List[str] = Field(
        default=[
            "Both A and R are true and R is correct explanation of A",
            "Both A and R are true but R is not correct explanation of A",
            "A is true but R is false",
            "A is false but R is true"
        ],
        description="Standard assertion-reasoning options"
    )
    correct_answer: str = Field(..., description="Correct answer (A/B/C/D)")
    explanation: str = Field(..., description="Detailed explanation of assertion and reasoning")


class MatchFollowingQuestion(BaseModel):
    """Match the following question structure"""
    instructions: str = Field(..., description="Instructions for matching")
    column_a: List[str] = Field(..., min_items=4, max_items=4, description="Items in Column A")
    column_b: List[str] = Field(..., min_items=4, max_items=4, description="Items in Column B")
    correct_matches: Dict[str, str] = Field(..., description="Correct matching pairs")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Coded answer options")
    correct_answer: str = Field(..., description="Correct coded answer")
    explanation: str = Field(..., description="Explanation of correct matches")


class CaseBasedQuestion(BaseModel):
    """Case-based question for legal reasoning"""
    case_scenario: str = Field(..., description="Legal scenario or case facts")
    question: str = Field(..., description="Question based on the scenario")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Answer options")
    correct_answer: str = Field(..., description="Correct answer")
    legal_principles: List[str] = Field(..., description="Legal principles involved")
    explanation: str = Field(..., description="Legal reasoning and constitutional provisions")


class LegalQuestionContent(BaseModel):
    """Wrapper for different question types"""
    question_type: LegalQuestionType = Field(..., description="Type of question")
    content: Union[
        MultipleChoiceQuestion,
        AssertionReasoningQuestion,
        MatchFollowingQuestion,
        CaseBasedQuestion,
        Dict[str, Any]  # For other question types
    ] = Field(..., description="Question content based on type")


class GeneratedQuestion(BaseModel):
    """Single generated question with metadata"""
    id: str = Field(..., description="Unique question identifier")
    question_type: LegalQuestionType = Field(..., description="Type of question")
    difficulty: DifficultyLevel = Field(..., description="Difficulty level")
    exam_type: ExamType = Field(..., description="Target exam type")

    # Question content
    content: LegalQuestionContent = Field(..., description="Question content")

    # Metadata
    topics: List[ConstitutionalTopic] = Field(..., description="Constitutional topics covered")
    articles_referenced: List[str] = Field(default=[], description="Constitutional articles referenced")
    parts_referenced: List[str] = Field(default=[], description="Constitutional parts referenced")

    # Educational metadata
    learning_objectives: List[str] = Field(default=[], description="What students should learn")
    key_concepts: List[str] = Field(default=[], description="Key constitutional concepts")
    related_cases: List[str] = Field(default=[], description="Related landmark cases")

    # Quality metrics
    estimated_time_minutes: int = Field(..., ge=1, le=10, description="Estimated solving time")
    cognitive_level: str = Field(..., description="Bloom's taxonomy level (Knowledge/Comprehension/Application/Analysis)")


class LegalQuestionGenerationRequest(BaseModel):
    """Request for generating legal questions"""
    # Basic parameters
    exam_type: ExamType = Field(..., description="Target exam type")
    question_types: List[LegalQuestionType] = Field(..., description="Types of questions to generate")
    count: int = Field(..., ge=1, le=20, description="Number of questions to generate")
    difficulty_distribution: Optional[Dict[DifficultyLevel, int]] = Field(
        None, description="Custom difficulty distribution (e.g., {easy: 5, medium: 3, hard: 2})"
    )

    # Content filters
    filters: Optional[LegalQuestionFilters] = Field(None, description="Content filtering options")

    # Quality controls
    avoid_repetition: bool = Field(True, description="Avoid similar questions")
    ensure_variety: bool = Field(True, description="Ensure topic variety")
    include_explanations: bool = Field(True, description="Include detailed explanations")

    # Educational parameters
    target_audience: str = Field(
        default="law_students",
        description="Target audience (law_students, exam_aspirants, professionals)"
    )
    time_limit_minutes: Optional[int] = Field(
        None, ge=30, le=300, description="Total time limit for all questions"
    )

    @validator('difficulty_distribution')
    def validate_difficulty_distribution(cls, v, values):
        if v and 'count' in values:
            total_difficulty = sum(v.values())
            if total_difficulty != values['count']:
                raise ValueError("Difficulty distribution must sum to total count")
        return v

    @validator('question_types')
    def validate_question_types(cls, v):
        if not v:
            raise ValueError("At least one question type must be specified")
        return v


class LegalQuestionGenerationResponse(BaseModel):
    """Response containing generated legal questions"""
    # Generated questions
    questions: List[GeneratedQuestion] = Field(..., description="Generated questions")

    # Request metadata
    exam_type: ExamType = Field(..., description="Target exam type")
    total_questions: int = Field(..., description="Total number of questions generated")

    # Content analysis
    topics_covered: List[ConstitutionalTopic] = Field(..., description="All topics covered")
    articles_covered: List[str] = Field(default=[], description="Constitutional articles covered")
    difficulty_breakdown: Dict[DifficultyLevel, int] = Field(..., description="Questions per difficulty")
    question_type_breakdown: Dict[LegalQuestionType, int] = Field(..., description="Questions per type")

    # Educational metadata
    estimated_total_time_minutes: int = Field(..., description="Estimated total solving time")
    learning_outcomes: List[str] = Field(..., description="Expected learning outcomes")
    suggested_study_materials: List[str] = Field(default=[], description="Recommended study resources")

    # Quality metrics
    generation_quality_score: float = Field(..., ge=0.0, le=1.0, description="Quality score (0-1)")
    coverage_score: float = Field(..., ge=0.0, le=1.0, description="Topic coverage score")

    # Processing metadata
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    generation_timestamp: str = Field(..., description="When questions were generated")


class QuestionValidationResult(BaseModel):
    """Validation result for generated questions"""
    is_valid: bool = Field(..., description="Overall validation status")
    question_id: str = Field(..., description="Question identifier")

    # Validation details
    grammar_check: bool = Field(..., description="Grammar and language validation")
    factual_accuracy: bool = Field(..., description="Factual accuracy check")
    constitutional_accuracy: bool = Field(..., description="Constitutional provisions accuracy")
    difficulty_appropriateness: bool = Field(..., description="Difficulty level appropriateness")

    # Issues found
    issues: List[str] = Field(default=[], description="Validation issues identified")
    suggestions: List[str] = Field(default=[], description="Improvement suggestions")

    # Quality score
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")


class LegalQuestionBankRequest(BaseModel):
    """Request for creating a question bank"""
    bank_name: str = Field(..., description="Name of the question bank")
    description: str = Field(..., description="Description of the question bank")

    # Bank composition
    total_questions: int = Field(..., ge=50, le=500, description="Total questions in bank")
    exam_types: List[ExamType] = Field(..., description="Target exam types")

    # Topic distribution
    topic_distribution: Dict[ConstitutionalTopic, int] = Field(
        ..., description="Questions per constitutional topic"
    )

    # Quality requirements
    min_quality_score: float = Field(
        default=0.8, ge=0.5, le=1.0, description="Minimum quality score for questions"
    )
    ensure_comprehensive_coverage: bool = Field(
        True, description="Ensure all major topics are covered"
    )

    # Export options
    export_format: str = Field(
        default="json", description="Export format (json, excel, pdf)"
    )

    @validator('topic_distribution')
    def validate_topic_distribution(cls, v, values):
        if v and 'total_questions' in values:
            total_distributed = sum(v.values())
            if total_distributed != values['total_questions']:
                raise ValueError("Topic distribution must sum to total questions")
        return v