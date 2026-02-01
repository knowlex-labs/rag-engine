from fastapi import APIRouter, Header, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from services.collection_task_service import collection_task_service
from services.collection_service import CollectionService
from services.query_service import QueryService
from models.api_models import QueryAnswerRequest, QueryResponse, CollectionStatusRequest, FileStatusResponse, BatchLinkRequest, IngestionResponse
from models.question_models import QuestionGenerationResponse

router = APIRouter(prefix="/api/v1/collections")
logger = logging.getLogger(__name__)
query_service = QueryService()
collection_service = CollectionService()

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

@router.post("/{collection_id}/status", response_model=List[FileStatusResponse])
async def get_collection_status(
    collection_id: str,
    request: CollectionStatusRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
):
    """
    Check the indexing status of files within a specific collection.

    Returns status information for each file_id:
    - INDEXED: File is successfully indexed with chunk count
    - NOT_FOUND: File not found in the collection
    - ERROR: Error occurred while checking status
    """
    try:
        status_results = collection_service.check_collection_status(
            user_id=x_user_id,
            collection_id=collection_id,
            file_ids=request.file_ids
        )

        return [FileStatusResponse(**result) for result in status_results]

    except Exception as e:
        logger.error(f"Error checking collection status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
