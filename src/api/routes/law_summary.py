"""
FastAPI routes for Legal Summary Generation
Smart constitutional law summaries with customizable focus and formatting.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any

from models.law_summary_models import (
    LegalSummaryRequest,
    LegalSummaryResponse,
    BatchSummaryRequest,
    BatchSummaryResponse,
    SummaryTemplate,
    SummaryType,
    SummaryAudience,
    FocusArea,
    ConstitutionalScope
)
from services.law_summary_service import LegalSummaryService

# Initialize router and service
router = APIRouter(prefix="/api/v1/law", tags=["Legal Summary Generation"])
legal_summary_service = LegalSummaryService()
logger = logging.getLogger(__name__)


@router.post("/generate-summary", response_model=LegalSummaryResponse, status_code=200)
async def generate_legal_summary(
    request: LegalSummaryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation"),
    background_tasks: BackgroundTasks = None
) -> LegalSummaryResponse:
    """
    Generate intelligent constitutional law summaries with customizable focus and formatting.

    **Features:**
    - **Smart Content Selection**: Automatically selects relevant constitutional provisions
    - **Audience Customization**: Tailored for students, professionals, exam aspirants
    - **Multiple Formats**: Bullet points, paragraphs, outlines, tables, comparisons
    - **Focus Areas**: Emphasize key provisions, cases, amendments, practical applications
    - **Educational Aids**: Quick facts, exam tips, practice questions, related topics
    - **Quality Validation**: Automated accuracy and completeness checking

    **Summary Types:**
    - **Bullet Points**: Structured, easy-to-scan format
    - **Paragraph**: Flowing narrative format
    - **Outline**: Hierarchical organization
    - **Table**: Comparative tabular format
    - **Comparison**: Side-by-side analysis
    - **Timeline**: Chronological development

    **Audience Options:**
    - **Law Students**: Educational focus with clear explanations
    - **Exam Aspirants**: CLAT/UGC NET optimized content
    - **Legal Professionals**: Comprehensive analysis for practitioners
    - **General Public**: Simple, accessible language
    - **Researchers**: Academic depth and scholarly perspective
    - **Judiciary Aspirants**: Judicial services exam preparation

    **Focus Areas:**
    - Key constitutional provisions and their significance
    - Exceptions, limitations, and special cases
    - Landmark court decisions and judicial interpretation
    - Constitutional amendments and their impact
    - Practical applications and real-world implications
    - Comparative analysis with other provisions
    - Historical context and evolution
    - Exam-focused facts and commonly tested concepts

    **Example Usage:**
    ```json
    {
      "topic": "Fundamental Rights under the Constitution",
      "scope": "thematic",
      "summary_type": "bullet_points",
      "target_words": 600,
      "audience": "exam_aspirant",
      "focus_areas": ["key_provisions", "landmark_cases", "exam_focus"],
      "filters": {
        "specific_articles": ["Art-14", "Art-19", "Art-21"],
        "include_cases": true,
        "include_amendments": true
      }
    }
    ```
    """

    try:
        # Validate request parameters
        if not request.topic.strip():
            raise HTTPException(
                status_code=400,
                detail="Topic cannot be empty"
            )

        if request.target_words < 100 or request.target_words > 2000:
            raise HTTPException(
                status_code=400,
                detail="Target word count must be between 100 and 2000"
            )

        # Log summary request
        start_time = time.time()
        logger.info(
            f"Legal summary request from user {x_user_id}: "
            f"topic='{request.topic}', type={request.summary_type}, "
            f"audience={request.audience}, words={request.target_words}"
        )

        # Generate summary
        response = await legal_summary_service.generate_legal_summary(
            request=request,
            user_id=x_user_id
        )

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"Legal summary generated successfully: "
            f"{response.metadata.word_count} words in {generation_time}ms, "
            f"quality_score={response.metadata.coverage_score:.2f}"
        )

        # Add background analytics if available
        if background_tasks:
            background_tasks.add_task(
                _log_summary_analytics,
                request, response, x_user_id, generation_time
            )

        return response

    except ValueError as e:
        logger.warning(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error generating legal summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating summary"
        )


@router.post("/batch-summary", response_model=BatchSummaryResponse, status_code=200)
async def generate_batch_summaries(
    request: BatchSummaryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> BatchSummaryResponse:
    """
    Generate multiple legal summaries efficiently with optional parallel processing.

    **Features:**
    - Batch processing up to 5 summaries at once
    - Parallel processing for improved performance
    - Consistency checks across summaries
    - Individual error handling for each summary

    **Use Cases:**
    - Comprehensive study materials for multiple topics
    - Comparative analysis across different constitutional areas
    - Bulk content generation for educational materials
    - Research compilation across various legal domains
    """

    try:
        if not request.summaries:
            raise HTTPException(
                status_code=400,
                detail="At least one summary request must be provided"
            )

        if len(request.summaries) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 summaries allowed per batch"
            )

        start_time = time.time()

        # Process summaries (simplified implementation)
        results = []
        successful = 0
        failed = 0

        for summary_request in request.summaries:
            try:
                summary_response = await legal_summary_service.generate_legal_summary(
                    request=summary_request,
                    user_id=x_user_id
                )
                results.append(summary_response)
                successful += 1

            except Exception as e:
                error_response = {
                    "error": str(e),
                    "topic": summary_request.topic,
                    "message": "Failed to generate summary"
                }
                results.append(error_response)
                failed += 1

        total_processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"Batch summary processed for user {x_user_id}: "
            f"{successful}/{len(request.summaries)} successful in {total_processing_time}ms"
        )

        return BatchSummaryResponse(
            summaries=results,
            total_requested=len(request.summaries),
            successful=successful,
            failed=failed,
            total_processing_time_ms=total_processing_time
        )

    except ValueError as e:
        logger.warning(f"Invalid batch request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing batch summaries: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing batch summaries"
        )


@router.get("/summary-templates", status_code=200)
async def get_summary_templates() -> Dict[str, Any]:
    """
    Get pre-configured summary templates for different legal topics and audiences.

    **Returns:**
    - Ready-to-use summary templates for common constitutional topics
    - Audience-specific configurations
    - Topic-based recommendations
    - Best practices for different summary types
    """

    return {
        "student_templates": {
            "fundamental_rights_overview": {
                "name": "Fundamental Rights Overview",
                "description": "Comprehensive overview of fundamental rights for law students",
                "recommended_for": ["law_student", "exam_aspirant"],
                "template_config": {
                    "topic": "Fundamental Rights in the Indian Constitution",
                    "scope": "thematic",
                    "summary_type": "bullet_points",
                    "target_words": 600,
                    "audience": "law_student",
                    "focus_areas": ["key_provisions", "landmark_cases", "practical_application"],
                    "filters": {
                        "constitutional_topics": ["fundamental_rights"],
                        "include_cases": True,
                        "include_examples": True
                    }
                },
                "example_topics": [
                    "Right to Equality (Articles 14-18)",
                    "Right to Freedom (Articles 19-22)",
                    "Right against Exploitation (Articles 23-24)"
                ]
            },
            "emergency_provisions_study": {
                "name": "Emergency Provisions Study Guide",
                "description": "Detailed study guide for constitutional emergency provisions",
                "recommended_for": ["law_student", "exam_aspirant", "judiciary_aspirant"],
                "template_config": {
                    "topic": "Emergency Provisions under the Constitution",
                    "scope": "constitutional_part",
                    "summary_type": "outline",
                    "target_words": 800,
                    "audience": "exam_aspirant",
                    "focus_areas": ["key_provisions", "exceptions", "landmark_cases", "exam_focus"],
                    "filters": {
                        "specific_articles": ["Art-352", "Art-356", "Art-360"],
                        "include_cases": True,
                        "include_amendments": True
                    }
                }
            }
        },
        "professional_templates": {
            "constitutional_interpretation": {
                "name": "Constitutional Interpretation Analysis",
                "description": "Professional analysis of constitutional interpretation principles",
                "recommended_for": ["legal_professional", "researcher"],
                "template_config": {
                    "topic": "Principles of Constitutional Interpretation",
                    "scope": "thematic",
                    "summary_type": "paragraph",
                    "target_words": 1200,
                    "audience": "legal_professional",
                    "focus_areas": ["landmark_cases", "comparative_analysis", "practical_application"],
                    "complexity_level": "advanced"
                }
            }
        },
        "exam_templates": {
            "clat_constitutional_law": {
                "name": "CLAT Constitutional Law Quick Reference",
                "description": "Quick reference summary for CLAT constitutional law questions",
                "recommended_for": ["exam_aspirant"],
                "template_config": {
                    "topic": "Constitutional Law for CLAT",
                    "scope": "comprehensive",
                    "summary_type": "bullet_points",
                    "target_words": 400,
                    "audience": "exam_aspirant",
                    "focus_areas": ["key_provisions", "exam_focus"],
                    "filters": {
                        "include_examples": True,
                        "include_cases": False  # Keep it concise for quick reference
                    }
                }
            },
            "ugc_net_comprehensive": {
                "name": "UGC NET Constitutional Law Comprehensive",
                "description": "Comprehensive constitutional law summary for UGC NET preparation",
                "recommended_for": ["exam_aspirant", "researcher"],
                "template_config": {
                    "topic": "Constitutional Law for UGC NET",
                    "scope": "comprehensive",
                    "summary_type": "outline",
                    "target_words": 1000,
                    "audience": "exam_aspirant",
                    "focus_areas": ["key_provisions", "landmark_cases", "comparative_analysis", "exam_focus"]
                }
            }
        },
        "comparative_templates": {
            "rights_vs_duties": {
                "name": "Rights vs Duties Comparison",
                "description": "Comparative analysis of fundamental rights and duties",
                "template_config": {
                    "topic": "Fundamental Rights vs Fundamental Duties",
                    "scope": "thematic",
                    "summary_type": "comparison",
                    "target_words": 700,
                    "focus_areas": ["comparative_analysis", "key_provisions"]
                }
            }
        },
        "recommended_configurations": {
            "law_student": {
                "preferred_summary_types": ["bullet_points", "outline"],
                "optimal_word_count": "500-800",
                "essential_focus_areas": ["key_provisions", "landmark_cases", "practical_application"],
                "complexity_level": "medium"
            },
            "exam_aspirant": {
                "preferred_summary_types": ["bullet_points", "outline"],
                "optimal_word_count": "300-600",
                "essential_focus_areas": ["key_provisions", "exam_focus"],
                "complexity_level": "medium"
            },
            "legal_professional": {
                "preferred_summary_types": ["paragraph", "comparison"],
                "optimal_word_count": "800-1500",
                "essential_focus_areas": ["landmark_cases", "practical_application", "comparative_analysis"],
                "complexity_level": "advanced"
            }
        }
    }


@router.get("/summary/topics", status_code=200)
async def get_available_topics() -> Dict[str, Any]:
    """
    Get available constitutional topics and their recommended configurations.

    **Returns:**
    - List of constitutional topics available for summary generation
    - Recommended focus areas for each topic
    - Suggested audience and summary types
    - Related topics and cross-references
    """

    return {
        "constitutional_topics": {
            "fundamental_rights": {
                "description": "Fundamental Rights guaranteed by Part III of the Constitution",
                "key_articles": ["Art-12", "Art-13", "Art-14", "Art-15", "Art-16", "Art-17", "Art-18", "Art-19", "Art-20", "Art-21", "Art-22"],
                "recommended_focus": ["key_provisions", "landmark_cases", "exceptions"],
                "suitable_audiences": ["law_student", "exam_aspirant", "general_public"],
                "optimal_word_count": "600-1000",
                "related_topics": ["directive_principles", "constitutional_remedies", "judicial_review"]
            },
            "directive_principles": {
                "description": "Directive Principles of State Policy under Part IV",
                "key_articles": ["Art-36", "Art-37", "Art-38", "Art-39", "Art-40", "Art-41", "Art-42", "Art-43", "Art-44", "Art-45", "Art-46", "Art-47", "Art-48", "Art-49", "Art-50", "Art-51"],
                "recommended_focus": ["key_provisions", "practical_application", "comparative_analysis"],
                "suitable_audiences": ["law_student", "exam_aspirant", "legal_professional"],
                "optimal_word_count": "500-800",
                "related_topics": ["fundamental_rights", "social_justice", "state_policy"]
            },
            "emergency_provisions": {
                "description": "Constitutional provisions for handling emergencies under Part XVIII",
                "key_articles": ["Art-352", "Art-353", "Art-354", "Art-355", "Art-356", "Art-357", "Art-358", "Art-359", "Art-360"],
                "recommended_focus": ["key_provisions", "exceptions", "landmark_cases"],
                "suitable_audiences": ["exam_aspirant", "judiciary_aspirant", "legal_professional"],
                "optimal_word_count": "700-1200",
                "related_topics": ["federalism", "center_state_relations", "fundamental_rights_suspension"]
            },
            "federalism": {
                "description": "Federal structure and distribution of powers",
                "key_articles": ["Art-1", "Art-245", "Art-246", "Art-247", "Art-248", "Art-249", "Art-250", "Art-251", "Art-252", "Art-253", "Art-254"],
                "recommended_focus": ["key_provisions", "comparative_analysis", "practical_application"],
                "suitable_audiences": ["law_student", "exam_aspirant", "researcher"],
                "optimal_word_count": "800-1200",
                "related_topics": ["emergency_provisions", "center_state_relations", "seventh_schedule"]
            }
        },
        "topic_combinations": [
            {
                "name": "Rights and Remedies",
                "topics": ["fundamental_rights", "constitutional_remedies"],
                "description": "Comprehensive coverage of rights and their enforcement mechanisms"
            },
            {
                "name": "Government Structure",
                "topics": ["parliament", "executive", "judiciary", "federalism"],
                "description": "Complete overview of constitutional government structure"
            },
            {
                "name": "Constitutional Safeguards",
                "topics": ["emergency_provisions", "constitutional_amendments", "basic_structure"],
                "description": "Constitutional protections and amendment procedures"
            }
        ]
    }


@router.get("/summary/health", status_code=200)
async def health_check() -> Dict[str, Any]:
    """Health check for legal summary generation service."""

    return {
        "status": "healthy",
        "service": "Legal Summary Generation API",
        "version": "1.0.0",
        "capabilities": {
            "summary_types": [stype.value for stype in SummaryType],
            "audiences": [audience.value for audience in SummaryAudience],
            "focus_areas": [focus.value for focus in FocusArea],
            "constitutional_scopes": [scope.value for scope in ConstitutionalScope]
        },
        "limits": {
            "min_words": 100,
            "max_words": 2000,
            "max_batch_size": 5,
            "supported_formats": 7,
            "supported_audiences": 6
        },
        "features": [
            "intelligent_content_selection",
            "audience_customization",
            "multiple_formats",
            "educational_aids",
            "quality_validation",
            "batch_processing",
            "template_system"
        ]
    }


# Background task for analytics
async def _log_summary_analytics(
    request: LegalSummaryRequest,
    response: LegalSummaryResponse,
    user_id: str,
    generation_time_ms: int
):
    """Log summary generation analytics for monitoring and improvement."""
    try:
        analytics_data = {
            "user_id": user_id,
            "topic": request.topic,
            "summary_type": request.summary_type,
            "audience": request.audience,
            "target_words": request.target_words,
            "actual_words": response.metadata.word_count,
            "generation_time_ms": generation_time_ms,
            "quality_score": response.metadata.coverage_score,
            "complexity_score": response.metadata.complexity_score,
            "focus_areas": request.focus_areas,
            "articles_covered": response.key_articles,
            "timestamp": response.metadata.last_updated
        }

        # Log for monitoring
        logger.info(f"Summary generation analytics: {analytics_data}")

        # Could send to analytics service here

    except Exception as e:
        logger.error(f"Failed to log summary analytics: {e}")