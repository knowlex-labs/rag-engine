"""
FastAPI routes for Indian Law Query System
Handles constitutional questions, BNS queries, and legal document search.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Header, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Union

from models.law_query_models import (
    LawQueryRequest,
    LawQueryResponse,
    LawQueryError,
    BatchLawQueryRequest,
    BatchLawQueryResponse,
    LegalDocumentType,
    AnswerStyle
)
from services.law_query_service import LawQueryService, BatchLawQueryService

# Initialize router and services
router = APIRouter(prefix="/api/v1/law", tags=["Legal Query"])
law_query_service = LawQueryService()
batch_query_service = BatchLawQueryService()
logger = logging.getLogger(__name__)


@router.post("/query", response_model=LawQueryResponse, status_code=200)
async def query_legal_document(
    request: LawQueryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> LawQueryResponse:
    """
    Query Indian legal documents (Constitution, BNS) with intelligent context retrieval.

    **Features:**
    - Constitutional question answering with article references
    - Multi-document search (Constitution + BNS ready)
    - Customizable answer styles for different audiences
    - Source attribution with relevance scoring
    - Related legal concepts extraction
    - Confidence metrics and quality assessment

    **Use Cases:**
    - Law student exam preparation (CLAT, UGC NET)
    - Legal research and case preparation
    - Constitutional law education
    - Quick legal reference lookup

    **Example Queries:**
    - "What are fundamental rights under Article 19?"
    - "Explain the emergency provisions in the Constitution"
    - "What is the difference between Article 14 and Article 15?"
    - "How does federalism work in India?"
    """

    try:
        # Validate request
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )

        # Process the legal query
        start_time = time.time()

        response = await law_query_service.process_legal_query(
            request=request,
            user_id=x_user_id
        )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(
            f"Legal query processed successfully for user {x_user_id} "
            f"in {processing_time}ms: {request.question[:50]}..."
        )

        return response

    except ValueError as e:
        logger.warning(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing legal query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing legal query"
        )


@router.post("/batch-query", response_model=BatchLawQueryResponse, status_code=200)
async def batch_query_legal_documents(
    request: BatchLawQueryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> BatchLawQueryResponse:
    """
    Process multiple legal queries efficiently with optional parallel processing.

    **Features:**
    - Batch processing up to 10 queries at once
    - Parallel processing for improved performance
    - Individual error handling for each query
    - Comprehensive batch metrics

    **Use Cases:**
    - Bulk legal research
    - Exam preparation with multiple topics
    - Comparative legal analysis
    - Educational content generation
    """

    try:
        if not request.queries:
            raise HTTPException(
                status_code=400,
                detail="At least one query must be provided"
            )

        if len(request.queries) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 queries allowed per batch"
            )

        start_time = time.time()

        # Process batch queries
        results = await batch_query_service.process_batch_queries(
            requests=request.queries,
            user_id=x_user_id,
            parallel=request.parallel_processing
        )

        # Calculate batch metrics
        successful_queries = sum(
            1 for result in results if isinstance(result, LawQueryResponse)
        )
        failed_queries = len(results) - successful_queries
        total_processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"Batch query processed for user {x_user_id}: "
            f"{successful_queries}/{len(results)} successful in {total_processing_time}ms"
        )

        return BatchLawQueryResponse(
            results=results,
            total_queries=len(request.queries),
            successful_queries=successful_queries,
            failed_queries=failed_queries,
            total_processing_time_ms=total_processing_time
        )

    except ValueError as e:
        logger.warning(f"Invalid batch request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing batch legal queries: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing batch queries"
        )


@router.get("/query/health", status_code=200)
async def health_check() -> dict:
    """
    Health check endpoint for the legal query service.

    **Returns:**
    - Service status
    - Available document types
    - Supported answer styles
    - System capabilities
    """

    try:
        return {
            "status": "healthy",
            "service": "Indian Law Query API",
            "version": "1.0.0",
            "capabilities": {
                "document_types": [doc_type.value for doc_type in LegalDocumentType],
                "answer_styles": [style.value for style in AnswerStyle],
                "features": [
                    "constitutional_query",
                    "source_attribution",
                    "concept_extraction",
                    "confidence_metrics",
                    "batch_processing",
                    "related_questions"
                ]
            },
            "limits": {
                "max_question_length": 1000,
                "max_answer_length": 2000,
                "max_sources": 10,
                "max_batch_size": 10,
                "max_context_chunks": 15
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@router.get("/query/examples", status_code=200)
async def get_query_examples() -> dict:
    """
    Get example queries for different legal topics and use cases.

    **Returns:**
    - Example queries by category
    - Suggested parameters
    - Best practices for query formulation
    """

    return {
        "constitutional_law": {
            "fundamental_rights": [
                "What are the fundamental rights guaranteed under Article 19?",
                "Explain the scope of Article 21 - Right to Life and Personal Liberty",
                "What is the difference between Article 14 and Article 16?",
                "How can fundamental rights be restricted during emergency?"
            ],
            "directive_principles": [
                "What are Directive Principles of State Policy?",
                "How do DPSPs differ from Fundamental Rights?",
                "What is the significance of Article 44?",
                "Explain the relationship between Articles 36-51"
            ],
            "emergency_provisions": [
                "What are the three types of emergencies in the Constitution?",
                "Explain Article 356 - President's Rule in States",
                "What is the procedure for declaring national emergency?",
                "How does emergency affect fundamental rights?"
            ],
            "federalism": [
                "How is power divided between Centre and States in India?",
                "What are the three lists in the Seventh Schedule?",
                "Explain the concept of cooperative federalism",
                "What is the role of Finance Commission in federalism?"
            ]
        },
        "exam_preparation": {
            "clat_questions": [
                "Which article guarantees equality before law?",
                "What is the minimum age for becoming Prime Minister?",
                "Under which article can the President dissolve Lok Sabha?",
                "What is the term of office of a High Court judge?"
            ],
            "ugc_net_questions": [
                "Analyze the basic structure doctrine in constitutional law",
                "Compare the Indian federal system with other federal constitutions",
                "Discuss the evolution of Article 21 through judicial interpretation",
                "Explain the constitutional provisions for protection of minorities"
            ]
        },
        "suggested_parameters": {
            "for_students": {
                "answer_style": "student_friendly",
                "include_sources": True,
                "include_related_concepts": True,
                "max_answer_length": 400
            },
            "for_professionals": {
                "answer_style": "professional",
                "include_confidence_metrics": True,
                "max_sources": 8,
                "max_answer_length": 800
            },
            "for_exam_prep": {
                "answer_style": "exam_prep",
                "include_related_concepts": True,
                "highlight_key_terms": True,
                "max_answer_length": 300
            }
        },
        "best_practices": [
            "Be specific about the constitutional provision or topic",
            "Use proper article numbers when available (e.g., 'Article 21')",
            "Specify the scope if comparing multiple provisions",
            "Choose appropriate answer style for your audience",
            "Include context for better understanding (e.g., 'in the context of emergency')"
        ]
    }