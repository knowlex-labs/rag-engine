"""
API Routes for UGC NET Question Generation
RESTful endpoints for intelligent question generation using Neo4j knowledge graphs.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

from models.question_models import (
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    QuestionGenerationError,
    DifficultyLevel,
    QuestionType
)
from services.enhanced_question_generator import enhanced_question_generator
from services.content_selector import content_selector
from api.api_constants import API_PREFIX

logger = logging.getLogger(__name__)

# Create router for question generation endpoints
router = APIRouter(prefix=f"{API_PREFIX}/questions", tags=["Question Generation"])


@router.post(
    "/generate",
    response_model=QuestionGenerationResponse,
    summary="Generate UGC NET Questions",
    description="""
    Generate intelligent UGC NET exam questions using Neo4j knowledge graphs.

    Supports:
    - Assertion-Reasoning questions
    - Match the Following questions
    - Comprehension-based questions

    Features:
    - 3-tier difficulty levels (Easy/Moderate/Difficult)
    - Graph-based smart content selection
    - Mixed question type batches
    - Quality validation and duplicate prevention
    """
)
async def generate_questions(
    request: QuestionGenerationRequest,
    background_tasks: BackgroundTasks
) -> QuestionGenerationResponse:
    """
    Generate UGC NET questions based on the provided specifications
    """
    try:
        # Log request for monitoring
        logger.info(
            f"Question generation request: "
            f"types={[q.type.value for q in request.questions]}, "
            f"total_count={sum(q.count for q in request.questions)}"
        )

        # Validate request
        validation_error = await _validate_generation_request(request)
        if validation_error:
            raise HTTPException(status_code=400, detail=validation_error)

        # Generate questions
        response = enhanced_question_generator.generate_questions(request)

        # Log response statistics
        logger.info(
            f"Question generation completed: "
            f"success={response.success}, "
            f"generated={response.total_generated}, "
            f"errors={len(response.errors)}"
        )

        # Add background task for cleanup/analytics if needed
        if response.success:
            background_tasks.add_task(_log_generation_analytics, request, response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Question generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Question generation failed: {str(e)}"
        )


@router.get(
    "/content-stats",
    summary="Get Content Statistics",
    description="Get statistics about available content for question generation"
)
async def get_content_statistics(
    collection_ids: Optional[str] = None,
    file_ids: Optional[str] = None,
    chunk_types: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get statistics about available content for question generation
    """
    try:
        # Parse comma-separated parameters
        filters = None
        if collection_ids or file_ids or chunk_types:
            from models.question_models import QuestionFilters
            filters = QuestionFilters(
                collection_ids=collection_ids.split(',') if collection_ids else None,
                file_ids=file_ids.split(',') if file_ids else None,
                chunk_types=chunk_types.split(',') if chunk_types else None
            )

        stats = content_selector.get_content_statistics(filters)

        return {
            "success": True,
            "statistics": stats,
            "message": "Content statistics retrieved successfully"
        }

    except Exception as e:
        logger.error(f"Failed to get content statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get content statistics: {str(e)}"
        )


@router.get(
    "/supported-types",
    summary="Get Supported Question Types",
    description="Get list of supported question types and difficulty levels"
)
async def get_supported_types() -> Dict[str, Any]:
    """
    Get information about supported question types and difficulty levels
    """
    return {
        "question_types": [
            {
                "type": "assertion_reasoning",
                "name": "Assertion-Reasoning",
                "description": "Questions with assertion and reason statements following UGC NET format",
                "typical_time": "2-4 minutes"
            },
            {
                "type": "match_following",
                "name": "Match the Following",
                "description": "Match items from List I with List II based on legal relationships",
                "typical_time": "2-4 minutes"
            },
            {
                "type": "comprehension",
                "name": "Comprehension",
                "description": "Passage-based questions testing understanding and analysis",
                "typical_time": "5-10 minutes"
            }
        ],
        "difficulty_levels": [
            {
                "level": "easy",
                "name": "Easy",
                "description": "Basic concepts, direct relationships, factual recall",
                "characteristics": ["Clear language", "Direct concept-definition", "Factual accuracy"]
            },
            {
                "level": "moderate",
                "name": "Moderate",
                "description": "Moderate complexity, some analysis required",
                "characteristics": ["Conditional language", "Application-based", "Some legal terminology"]
            },
            {
                "level": "difficult",
                "name": "Difficult",
                "description": "Complex legal principles, deep analysis required",
                "characteristics": ["Complex terminology", "Exception handling", "Nuanced reasoning"]
            }
        ],
        "filters": [
            "collection_ids",
            "file_ids",
            "entities",
            "relationships",
            "chunk_types",
            "chapters",
            "key_terms"
        ]
    }


@router.post(
    "/validate-content",
    summary="Validate Content for Question Generation",
    description="Check if sufficient content is available for the specified question requirements"
)
async def validate_content_availability(
    request: QuestionGenerationRequest
) -> Dict[str, Any]:
    """
    Validate if sufficient content is available for generating the requested questions
    """
    try:
        validation_results = []
        overall_feasible = True

        for question_request in request.questions:
            # Check content availability for this specific request
            content_result = content_selector.select_content_for_question(
                question_request.type,
                question_request.difficulty,
                question_request.filters,
                question_request.count
            )

            sufficient_content = len(content_result.selected_chunks) >= question_request.count
            if not sufficient_content:
                overall_feasible = False

            validation_results.append({
                "question_type": question_request.type.value,
                "difficulty": question_request.difficulty.value,
                "requested_count": question_request.count,
                "available_chunks": len(content_result.selected_chunks),
                "sufficient_content": sufficient_content,
                "selection_strategy": content_result.selection_strategy,
                "recommendations": _get_content_recommendations(content_result, question_request)
            })

        return {
            "success": True,
            "overall_feasible": overall_feasible,
            "validation_results": validation_results,
            "message": "Content validation completed"
        }

    except Exception as e:
        logger.error(f"Content validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Content validation failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health Check",
    description="Check if question generation service is healthy"
)
async def health_check() -> Dict[str, Any]:
    """
    Health check for question generation service
    """
    try:
        # Test basic functionality
        from services.graph_service import graph_service

        # Check Neo4j connection
        graph_service.verify_connection()

        # Check content availability
        stats = content_selector.get_content_statistics()

        return {
            "status": "healthy",
            "neo4j_connected": True,
            "total_chunks": stats.get("total_chunks", 0),
            "unique_files": stats.get("unique_files", 0),
            "service_ready": True,
            "timestamp": str(datetime.now())
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": str(datetime.now())
        }


# Helper Functions

async def _validate_generation_request(request: QuestionGenerationRequest) -> Optional[str]:
    """
    Validate the question generation request
    """
    # Check total question limit
    total_questions = sum(q.count for q in request.questions)
    if total_questions > 20:
        return "Total questions cannot exceed 20 per request"

    # Check individual question counts
    for q in request.questions:
        if q.count < 1 or q.count > 10:
            return f"Question count must be between 1 and 10, got {q.count}"

    # Validate question types
    supported_types = [QuestionType.ASSERTION_REASONING, QuestionType.MATCH_FOLLOWING, QuestionType.COMPREHENSION]
    for q in request.questions:
        if q.type not in supported_types:
            return f"Unsupported question type: {q.type}"

    # Validate difficulty levels
    supported_difficulties = [DifficultyLevel.EASY, DifficultyLevel.MODERATE, DifficultyLevel.DIFFICULT]
    for q in request.questions:
        if q.difficulty not in supported_difficulties:
            return f"Unsupported difficulty level: {q.difficulty}"

    return None


def _get_content_recommendations(content_result, question_request) -> List[str]:
    """
    Generate recommendations based on content availability
    """
    recommendations = []

    if len(content_result.selected_chunks) == 0:
        recommendations.append("No suitable content found. Try broader filters or different collections.")

    elif len(content_result.selected_chunks) < question_request.count:
        recommendations.extend([
            f"Only {len(content_result.selected_chunks)} chunks available for {question_request.count} questions",
            "Consider reducing question count or expanding content filters",
            "Check if more documents are indexed in the specified collections"
        ])

    if question_request.type == QuestionType.COMPREHENSION and not any(
        len(chunk.text) > 800 for chunk in content_result.selected_chunks
    ):
        recommendations.append("Content chunks may be too short for comprehension questions")

    return recommendations


async def _log_generation_analytics(request: QuestionGenerationRequest, response: QuestionGenerationResponse):
    """
    Background task to log generation analytics
    """
    try:
        analytics_data = {
            "timestamp": datetime.now().isoformat(),
            "request_summary": {
                "total_requested": sum(q.count for q in request.questions),
                "types_requested": [q.type.value for q in request.questions],
                "difficulties": [q.difficulty.value for q in request.questions]
            },
            "response_summary": {
                "success": response.success,
                "total_generated": response.total_generated,
                "generation_stats": response.generation_stats,
                "error_count": len(response.errors)
            }
        }

        logger.info(f"Question generation analytics: {analytics_data}")

    except Exception as e:
        logger.error(f"Failed to log analytics: {e}")


# Import datetime for health check
from datetime import datetime