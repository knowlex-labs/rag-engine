"""
Pydantic models for Legal Summary Generation API
Smart constitutional law summaries with customizable focus and formatting.
"""

from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator


class SummaryType(str, Enum):
    """Types of legal summaries that can be generated"""
    BULLET_POINTS = "bullet_points"  # Structured bullet point format
    PARAGRAPH = "paragraph"  # Flowing paragraph format
    TABLE = "table"  # Tabular comparison format
    OUTLINE = "outline"  # Hierarchical outline format
    FLOWCHART = "flowchart"  # Process flow format
    COMPARISON = "comparison"  # Side-by-side comparison
    TIMELINE = "timeline"  # Chronological sequence


class SummaryAudience(str, Enum):
    """Target audience for summary customization"""
    LAW_STUDENT = "law_student"  # Law school students
    EXAM_ASPIRANT = "exam_aspirant"  # CLAT/UGC NET candidates
    LEGAL_PROFESSIONAL = "legal_professional"  # Practicing lawyers
    GENERAL_PUBLIC = "general_public"  # General audience
    RESEARCHER = "researcher"  # Academic researchers
    JUDICIARY_ASPIRANT = "judiciary_aspirant"  # Judicial service candidates


class FocusArea(str, Enum):
    """Areas of focus for summary content"""
    KEY_PROVISIONS = "key_provisions"  # Core constitutional provisions
    EXCEPTIONS = "exceptions"  # Exceptions and limitations
    LANDMARK_CASES = "landmark_cases"  # Important judicial decisions
    AMENDMENTS = "amendments"  # Constitutional amendments
    PRACTICAL_APPLICATION = "practical_application"  # Real-world applications
    COMPARATIVE_ANALYSIS = "comparative_analysis"  # Comparisons with other provisions
    HISTORICAL_CONTEXT = "historical_context"  # Historical background
    EXAM_FOCUS = "exam_focus"  # Exam-relevant points


class ConstitutionalScope(str, Enum):
    """Scope of constitutional content for summaries"""
    SPECIFIC_ARTICLE = "specific_article"  # Single article focus
    CONSTITUTIONAL_PART = "constitutional_part"  # Entire part (e.g., Part III)
    THEMATIC = "thematic"  # Thematic across multiple parts
    COMPREHENSIVE = "comprehensive"  # Broad constitutional overview


class SummaryFilters(BaseModel):
    """Filters for customizing summary content"""
    specific_articles: Optional[List[str]] = Field(
        None, description="Focus on specific articles (e.g., ['Art-21', 'Art-14'])"
    )
    constitutional_parts: Optional[List[str]] = Field(
        None, description="Focus on specific parts (e.g., ['Part III', 'Part IV'])"
    )
    topics: Optional[List[str]] = Field(
        None, description="Focus on specific topics (e.g., ['fundamental rights', 'emergency provisions'])"
    )
    include_cases: bool = Field(
        True, description="Include landmark case references"
    )
    include_amendments: bool = Field(
        True, description="Include amendment information"
    )
    include_examples: bool = Field(
        True, description="Include practical examples"
    )
    exclude_topics: Optional[List[str]] = Field(
        None, description="Topics to exclude from summary"
    )
    time_period: Optional[tuple[int, int]] = Field(
        None, description="Focus on specific time period for cases/amendments"
    )


class SummaryStructure(BaseModel):
    """Structure configuration for the summary"""
    include_introduction: bool = Field(True, description="Include introductory overview")
    include_key_points: bool = Field(True, description="Include key points section")
    include_details: bool = Field(True, description="Include detailed explanations")
    include_conclusion: bool = Field(True, description="Include concluding summary")
    include_references: bool = Field(True, description="Include article/case references")
    max_sections: Optional[int] = Field(None, ge=2, le=10, description="Maximum number of sections")


class LegalSummaryRequest(BaseModel):
    """Request model for generating legal summaries"""
    # Core content specification
    topic: str = Field(..., min_length=5, max_length=200, description="Main topic for summary")
    scope: ConstitutionalScope = Field(..., description="Scope of constitutional content")

    # Summary configuration
    summary_type: SummaryType = Field(default=SummaryType.BULLET_POINTS, description="Format of summary")
    target_words: int = Field(default=500, ge=100, le=2000, description="Target word count")
    audience: SummaryAudience = Field(default=SummaryAudience.LAW_STUDENT, description="Target audience")

    # Content customization
    focus_areas: List[FocusArea] = Field(
        default=[FocusArea.KEY_PROVISIONS],
        description="Areas to emphasize in summary"
    )
    filters: Optional[SummaryFilters] = Field(None, description="Content filtering options")
    structure: Optional[SummaryStructure] = Field(None, description="Summary structure preferences")

    # Quality controls
    ensure_accuracy: bool = Field(True, description="Ensure constitutional accuracy")
    include_source_verification: bool = Field(True, description="Include source verification")
    complexity_level: str = Field(
        default="medium",
        description="Complexity level (simple, medium, advanced)"
    )

    @validator('topic')
    def validate_topic(cls, v):
        if not v.strip():
            raise ValueError("Topic cannot be empty")
        return v.strip()

    @validator('focus_areas')
    def validate_focus_areas(cls, v):
        if not v:
            raise ValueError("At least one focus area must be specified")
        return v


class SummarySection(BaseModel):
    """Individual section within a summary"""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    subsections: Optional[List['SummarySection']] = Field(None, description="Nested subsections")
    references: List[str] = Field(default=[], description="Article/case references for this section")
    key_concepts: List[str] = Field(default=[], description="Key concepts covered")


class SummaryReference(BaseModel):
    """Reference to constitutional provision or case law"""
    type: str = Field(..., description="Type of reference (article, case, amendment)")
    reference: str = Field(..., description="Reference identifier")
    title: str = Field(..., description="Reference title")
    relevance: str = Field(..., description="Why this reference is relevant")
    url: Optional[str] = Field(None, description="Link to reference if available")


class SummaryMetadata(BaseModel):
    """Metadata about the generated summary"""
    word_count: int = Field(..., description="Actual word count")
    reading_time_minutes: int = Field(..., description="Estimated reading time")
    complexity_score: float = Field(..., ge=0.0, le=1.0, description="Complexity score (0-1)")
    coverage_score: float = Field(..., ge=0.0, le=1.0, description="Topic coverage score")
    accuracy_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in accuracy")
    last_updated: str = Field(..., description="When summary was generated")


class LegalSummaryResponse(BaseModel):
    """Response model for legal summaries"""
    # Core summary content
    title: str = Field(..., description="Summary title")
    content: str = Field(..., description="Main summary content")
    sections: List[SummarySection] = Field(default=[], description="Structured sections")

    # Request metadata
    topic: str = Field(..., description="Original topic requested")
    summary_type: SummaryType = Field(..., description="Summary format used")
    audience: SummaryAudience = Field(..., description="Target audience")

    # Content analysis
    key_articles: List[str] = Field(default=[], description="Key constitutional articles covered")
    key_concepts: List[str] = Field(default=[], description="Key legal concepts")
    landmark_cases: List[str] = Field(default=[], description="Landmark cases mentioned")
    constitutional_parts: List[str] = Field(default=[], description="Constitutional parts covered")

    # References and sources
    references: List[SummaryReference] = Field(default=[], description="Detailed references")
    suggested_reading: List[str] = Field(default=[], description="Additional reading suggestions")
    related_topics: List[str] = Field(default=[], description="Related constitutional topics")

    # Quality and utility metrics
    metadata: SummaryMetadata = Field(..., description="Summary metadata")

    # Educational aids
    quick_facts: List[str] = Field(default=[], description="Quick facts for memorization")
    exam_tips: List[str] = Field(default=[], description="Exam-specific tips")
    practice_questions: List[str] = Field(default=[], description="Sample practice questions")

    # Processing information
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class SummaryValidationResult(BaseModel):
    """Validation result for generated summaries"""
    is_valid: bool = Field(..., description="Overall validation status")

    # Validation criteria
    constitutional_accuracy: bool = Field(..., description="Accuracy of constitutional references")
    factual_accuracy: bool = Field(..., description="Factual accuracy of content")
    completeness: bool = Field(..., description="Completeness of coverage")
    clarity: bool = Field(..., description="Clarity and readability")
    audience_appropriateness: bool = Field(..., description="Appropriateness for target audience")

    # Issues and feedback
    issues_found: List[str] = Field(default=[], description="Issues identified")
    suggestions: List[str] = Field(default=[], description="Improvement suggestions")
    missing_elements: List[str] = Field(default=[], description="Important missing elements")

    # Quality metrics
    overall_quality: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    readability_score: float = Field(..., ge=0.0, le=1.0, description="Readability score")


class BatchSummaryRequest(BaseModel):
    """Request for generating multiple summaries"""
    summaries: List[LegalSummaryRequest] = Field(..., max_items=5, description="Multiple summary requests")
    ensure_consistency: bool = Field(True, description="Ensure consistency across summaries")
    parallel_processing: bool = Field(True, description="Process in parallel")


class BatchSummaryResponse(BaseModel):
    """Response for batch summary generation"""
    summaries: List[Union[LegalSummaryResponse, Dict[str, str]]] = Field(..., description="Generated summaries or errors")
    total_requested: int = Field(..., description="Total summaries requested")
    successful: int = Field(..., description="Successfully generated summaries")
    failed: int = Field(..., description="Failed summary generations")
    total_processing_time_ms: int = Field(..., description="Total processing time")


class SummaryTemplate(BaseModel):
    """Pre-configured summary template"""
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    recommended_for: List[SummaryAudience] = Field(..., description="Recommended audiences")
    template_config: LegalSummaryRequest = Field(..., description="Template configuration")
    example_topics: List[str] = Field(..., description="Example topics for this template")


class SummaryExportRequest(BaseModel):
    """Request for exporting summaries in different formats"""
    summary_id: str = Field(..., description="Summary identifier")
    export_format: str = Field(..., description="Export format (pdf, docx, markdown, html)")
    include_references: bool = Field(True, description="Include reference section")
    include_metadata: bool = Field(False, description="Include metadata section")
    custom_styling: Optional[Dict[str, str]] = Field(None, description="Custom styling options")


# Enable forward references
SummarySection.model_rebuild()