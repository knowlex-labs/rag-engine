from fastapi import APIRouter, Header, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from services.collection_task_service import collection_task_service
from services.query_service import QueryService
from models.api_models import QueryAnswerRequest, QueryResponse
from models.question_models import QuestionGenerationResponse

router = APIRouter(prefix="/api/v1/collections")
logger = logging.getLogger(__name__)
query_service = QueryService()

@router.post("/{collection_id}/chat", response_model=QueryResponse)
async def collection_chat(
    collection_id: str,
    request: QueryAnswerRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
):
    """
    Detailed chat about documents in a specific collection.
    """
    try:
        # Override collection_ids in request to ensure focus on this collection
        return query_service.search(
            collection_name=collection_id, # This is used as identifier in some logic
            query_text=request.query,
            limit=request.top_k,
            collection_ids=[collection_id],
            answer_style=request.answer_style or "detailed"
        )
    except Exception as e:
        logger.error(f"Error in collection chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/summary")
async def collection_summary(
    collection_id: str,
    x_user_id: str = Header(..., description="User ID for context isolation")
):
    """
    Generate a professional and high-quality summary of the collection.
    """
    try:
        return await collection_task_service.generate_summary(collection_id, x_user_id)
    except Exception as e:
        logger.error(f"Error generating collection summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{collection_id}/quiz", response_model=QuestionGenerationResponse)
async def collection_quiz(
    collection_id: str,
    num_questions: int = Query(10, ge=1, le=20),
    difficulty: str = Query("moderate", description="easy, moderate, difficult"),
    x_user_id: str = Header(..., description="User ID for context isolation")
):
    """
    Generate a mixed quiz (MCQ, Assertion-Reasoning, Match) from the collection.
    """
    try:
        return await collection_task_service.generate_quiz(collection_id, num_questions, difficulty)
    except Exception as e:
        logger.error(f"Error generating collection quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))
