"""
FastAPI routes for Legal Question Generation
Specialized endpoints for CLAT, UGC NET, and Judiciary exam question generation.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any

from models.law_question_models import (
    LegalQuestionGenerationRequest,
    LegalQuestionGenerationResponse,
    ExamType,
    LegalQuestionType,
    DifficultyLevel,
    ConstitutionalTopic,
    QuestionValidationResult
)
from services.enhanced_question_generator import enhanced_question_generator
from models.question_models import QuestionGenerationRequest, QuestionRequest, QuestionType, DifficultyLevel as GenDifficultyLevel

# Initialize router and service
router = APIRouter(prefix="/api/v1/law", tags=["Legal Question Generation"])
logger = logging.getLogger(__name__)


@router.post("/generate-questions", response_model=LegalQuestionGenerationResponse, status_code=200)
async def generate_legal_questions(
    request: LegalQuestionGenerationRequest,
    x_user_id: str = Header(..., description="User ID for context isolation"),
    background_tasks: BackgroundTasks = None
) -> LegalQuestionGenerationResponse:
    """
    Generate legal exam questions for CLAT, UGC NET, Judiciary and other law exams.

    **Features:**
    - **Exam-specific patterns**: Questions tailored for different exam types
    - **Constitutional focus**: Deep integration with Constitution of India content
    - **Multiple question types**: MCQs, Assertion-Reasoning, Case-based, Match-following
    - **Intelligent difficulty distribution**: Balanced across easy/medium/hard levels
    - **Source attribution**: Questions linked to specific constitutional articles
    - **Quality validation**: Automated validation for accuracy and relevance

    **Supported Exam Types:**
    - **CLAT**: Common Law Admission Test patterns
    - **UGC NET**: University Grants Commission NET Law
    - **Judiciary**: Judicial Services Examinations
    - **UPSC**: UPSC Law Optional patterns
    - **AILET**: All India Law Entrance Test

    **Question Types:**
    - **Multiple Choice**: Standard 4-option questions
    - **Assertion-Reasoning**: Popular in CLAT with A-R analysis
    - **Case-based**: Legal scenarios with application questions
    - **Match-following**: Articles/provisions matching
    - **Legal Reasoning**: Principle-based questions

    **Constitutional Topics:**
    - Fundamental Rights (Articles 12-35)
    - Directive Principles (Articles 36-51)
    - Emergency Provisions (Articles 352-360)
    - Federalism and Center-State Relations
    - Parliamentary System and Elections
    - Judiciary and Constitutional Courts
    - Constitutional Amendments and Basic Structure

    **Example Usage:**
    ```json
    {
      "exam_type": "clat",
      "question_types": ["multiple_choice", "assertion_reasoning"],
      "count": 10,
      "filters": {
        "constitutional_topics": ["fundamental_rights"],
        "specific_articles": ["Art-21", "Art-19"]
      },
      "target_audience": "law_students"
    }
    ```
    """

    try:
        # Validate request parameters
        if not request.question_types:
            raise HTTPException(
                status_code=400,
                detail="At least one question type must be specified"
            )

        if request.count < 1 or request.count > 20:
            raise HTTPException(
                status_code=400,
                detail="Question count must be between 1 and 20"
            )

        # Log generation request
        start_time = time.time()
        logger.info(
            f"Legal question generation request from user {x_user_id}: "
            f"exam={request.exam_type}, types={request.question_types}, count={request.count}"
        )

        # Generate questions
        response = await legal_question_service.generate_legal_questions(
            request=request,
            user_id=x_user_id
        )

        generation_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"Legal questions generated successfully: "
            f"{response.total_questions} questions in {generation_time}ms, "
            f"quality_score={response.generation_quality_score:.2f}"
        )

        # Add background analytics if available
        if background_tasks:
            background_tasks.add_task(
                _log_question_analytics,
                request, response, x_user_id, generation_time
            )

        return response

    except ValueError as e:
        logger.warning(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error generating legal questions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while generating questions"
        )


@router.get("/generate-questions/templates", status_code=200)
async def get_question_templates() -> Dict[str, Any]:
    """
    Get pre-configured question generation templates for different exam patterns.

    **Returns:**
    - Ready-to-use request templates for different exams
    - Recommended parameters for each exam type
    - Topic-specific configurations
    - Difficulty distribution suggestions
    """

    return {
        "clat_templates": {
            "constitutional_law_basics": {
                "exam_type": "clat",
                "question_types": ["multiple_choice", "assertion_reasoning"],
                "count": 10,
                "filters": {
                    "constitutional_topics": ["fundamental_rights", "directive_principles"],
                    "specific_articles": ["Art-14", "Art-19", "Art-21", "Art-32"]
                },
                "target_audience": "law_students",
                "time_limit_minutes": 15,
                "description": "Basic constitutional law for CLAT preparation"
            },
            "legal_reasoning": {
                "exam_type": "clat",
                "question_types": ["case_based", "legal_reasoning"],
                "count": 8,
                "filters": {
                    "constitutional_topics": ["fundamental_rights", "federalism"],
                    "landmark_cases": True
                },
                "difficulty_distribution": {"easy": 2, "medium": 4, "hard": 2},
                "description": "Legal reasoning questions for CLAT"
            }
        },
        "ugc_net_templates": {
            "comprehensive_constitutional": {
                "exam_type": "ugc_net",
                "question_types": ["multiple_choice", "assertion_reasoning", "match_following"],
                "count": 15,
                "filters": {
                    "constitutional_topics": ["fundamental_rights", "directive_principles", "emergency_provisions", "federalism"],
                    "comparative_analysis": True
                },
                "difficulty_distribution": {"easy": 3, "medium": 8, "hard": 4},
                "description": "Comprehensive constitutional law for UGC NET"
            },
            "advanced_constitutional_theory": {
                "exam_type": "ugc_net",
                "question_types": ["case_based", "short_answer"],
                "count": 10,
                "filters": {
                    "constitutional_topics": ["constitutional_amendments", "judiciary"],
                    "landmark_cases": True,
                    "amendments": True
                },
                "difficulty_distribution": {"medium": 4, "hard": 6},
                "description": "Advanced constitutional theory and jurisprudence"
            }
        },
        "judiciary_templates": {
            "judicial_services_prep": {
                "exam_type": "judiciary",
                "question_types": ["case_based", "legal_reasoning", "short_answer"],
                "count": 12,
                "filters": {
                    "constitutional_topics": ["fundamental_rights", "emergency_provisions", "judiciary"],
                    "landmark_cases": True,
                    "comparative_analysis": True
                },
                "difficulty_distribution": {"medium": 5, "hard": 7},
                "target_audience": "professionals",
                "description": "Judicial services examination preparation"
            }
        },
        "custom_templates": {
            "fundamental_rights_deep_dive": {
                "exam_type": "general",
                "question_types": ["multiple_choice", "assertion_reasoning", "case_based"],
                "count": 20,
                "filters": {
                    "constitutional_topics": ["fundamental_rights"],
                    "specific_articles": ["Art-14", "Art-15", "Art-16", "Art-19", "Art-20", "Art-21", "Art-22"],
                    "landmark_cases": True
                },
                "description": "Deep dive into fundamental rights"
            },
            "emergency_provisions_focus": {
                "exam_type": "general",
                "question_types": ["multiple_choice", "case_based"],
                "count": 10,
                "filters": {
                    "constitutional_topics": ["emergency_provisions"],
                    "specific_articles": ["Art-352", "Art-356", "Art-360"]
                },
                "description": "Emergency provisions comprehensive study"
            }
        },
        "recommended_settings": {
            "clat": {
                "time_per_question_minutes": 1.5,
                "preferred_difficulty": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
                "focus_areas": ["fundamental_rights", "legal_reasoning", "current_constitutional_developments"]
            },
            "ugc_net": {
                "time_per_question_minutes": 2.0,
                "preferred_difficulty": {"easy": 0.2, "medium": 0.5, "hard": 0.3},
                "focus_areas": ["constitutional_theory", "comparative_analysis", "jurisprudence"]
            },
            "judiciary": {
                "time_per_question_minutes": 3.0,
                "preferred_difficulty": {"easy": 0.1, "medium": 0.4, "hard": 0.5},
                "focus_areas": ["case_law", "legal_application", "procedural_knowledge"]
            }
        }
    }


@router.get("/generate-questions/topics", status_code=200)
async def get_constitutional_topics() -> Dict[str, Any]:
    """
    Get available constitutional topics and their coverage details.

    **Returns:**
    - List of all constitutional topics available for question generation
    - Articles covered under each topic
    - Key concepts and landmark cases
    - Recommended question types for each topic
    """

    return {
        "constitutional_topics": {
            ConstitutionalTopic.FUNDAMENTAL_RIGHTS: {
                "description": "Fundamental Rights guaranteed by the Constitution",
                "articles": ["Art-12", "Art-13", "Art-14", "Art-15", "Art-16", "Art-17", "Art-18", "Art-19", "Art-20", "Art-21", "Art-22"],
                "key_concepts": ["equality", "liberty", "due_process", "judicial_review", "positive_discrimination"],
                "landmark_cases": ["Maneka Gandhi", "Kesavananda Bharati", "Minerva Mills", "ADM Jabalpur"],
                "recommended_question_types": ["multiple_choice", "assertion_reasoning", "case_based"],
                "difficulty_range": ["easy", "medium", "hard"],
                "exam_relevance": ["clat", "ugc_net", "judiciary", "upsc"]
            },
            ConstitutionalTopic.DIRECTIVE_PRINCIPLES: {
                "description": "Directive Principles of State Policy for governance",
                "articles": ["Art-36", "Art-37", "Art-38", "Art-39", "Art-40", "Art-41", "Art-42", "Art-43", "Art-44", "Art-45", "Art-46", "Art-47", "Art-48", "Art-49", "Art-50", "Art-51"],
                "key_concepts": ["social_justice", "economic_welfare", "uniform_civil_code", "environmental_protection"],
                "landmark_cases": ["State of Madras v. Champakam", "Minerva Mills", "Unnikrishnan"],
                "recommended_question_types": ["multiple_choice", "assertion_reasoning", "match_following"],
                "difficulty_range": ["easy", "medium"],
                "exam_relevance": ["clat", "ugc_net", "upsc"]
            },
            ConstitutionalTopic.EMERGENCY_PROVISIONS: {
                "description": "Constitutional provisions for handling emergencies",
                "articles": ["Art-352", "Art-353", "Art-354", "Art-355", "Art-356", "Art-357", "Art-358", "Art-359", "Art-360"],
                "key_concepts": ["national_emergency", "presidential_rule", "financial_emergency", "fundamental_rights_suspension"],
                "landmark_cases": ["Minerva Mills", "44th Amendment case", "S.R. Bommai"],
                "recommended_question_types": ["case_based", "legal_reasoning", "assertion_reasoning"],
                "difficulty_range": ["medium", "hard"],
                "exam_relevance": ["ugc_net", "judiciary", "upsc"]
            },
            ConstitutionalTopic.FEDERALISM: {
                "description": "Federal structure and Center-State relations",
                "articles": ["Art-1", "Art-245", "Art-246", "Art-247", "Art-248", "Art-249", "Art-250", "Art-251", "Art-252", "Art-253", "Art-254"],
                "key_concepts": ["division_of_powers", "union_list", "state_list", "concurrent_list", "residuary_powers"],
                "landmark_cases": ["State of West Bengal v. Union of India", "S.R. Bommai", "I.R. Coelho"],
                "recommended_question_types": ["multiple_choice", "case_based", "match_following"],
                "difficulty_range": ["medium", "hard"],
                "exam_relevance": ["clat", "ugc_net", "judiciary"]
            }
        },
        "topic_combinations": [
            {
                "name": "Rights and Remedies",
                "topics": ["fundamental_rights", "judiciary"],
                "description": "Fundamental rights and their judicial enforcement"
            },
            {
                "name": "Governance Structure",
                "topics": ["parliament", "executive", "federalism"],
                "description": "Constitutional framework of governance"
            },
            {
                "name": "Constitutional Safeguards",
                "topics": ["emergency_provisions", "constitutional_amendments"],
                "description": "Safeguards and amendment procedures"
            }
        ],
        "difficulty_guidelines": {
            "easy": "Basic factual knowledge about constitutional provisions",
            "medium": "Understanding and application of constitutional principles",
            "hard": "Analysis, synthesis, and critical evaluation of constitutional concepts"
        }
    }


@router.get("/generate-questions/health", status_code=200)
async def health_check() -> Dict[str, Any]:
    """Health check for legal question generation service."""

    return {
        "status": "healthy",
        "service": "Legal Question Generation API",
        "version": "1.0.0",
        "capabilities": {
            "exam_types": [exam.value for exam in ExamType],
            "question_types": [qtype.value for qtype in LegalQuestionType],
            "constitutional_topics": [topic.value for topic in ConstitutionalTopic],
            "difficulty_levels": [diff.value for diff in DifficultyLevel]
        },
        "limits": {
            "max_questions_per_request": 20,
            "min_questions_per_request": 1,
            "supported_exams": 6,
            "constitutional_topics_available": len(ConstitutionalTopic)
        },
        "features": [
            "exam_specific_patterns",
            "constitutional_integration",
            "quality_validation",
            "source_attribution",
            "difficulty_distribution",
            "topic_filtering"
        ]
    }


# Background task for analytics
async def _log_question_analytics(
    request: LegalQuestionGenerationRequest,
    response: LegalQuestionGenerationResponse,
    user_id: str,
    generation_time_ms: int
):
    """Log question generation analytics for monitoring and improvement."""
    try:
        analytics_data = {
            "user_id": user_id,
            "exam_type": request.exam_type,
            "question_types": request.question_types,
            "requested_count": request.count,
            "generated_count": response.total_questions,
            "generation_time_ms": generation_time_ms,
            "quality_score": response.generation_quality_score,
            "coverage_score": response.coverage_score,
            "topics_covered": response.topics_covered,
            "articles_covered": response.articles_covered,
            "timestamp": response.generation_timestamp
        }

        # Log for monitoring
        logger.info(f"Question generation analytics: {analytics_data}")

        # Could send to analytics service here

    except Exception as e:
        logger.error(f"Failed to log question analytics: {e}")