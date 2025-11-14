from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Optional, Dict, Any
from models.api_models import ApiResponse, ApiResponseWithBody
from repositories.quiz_repository import quiz_repository
from services.quiz_job_service import quiz_job_service
from models.quiz_models import QuizResponse, QuizSubmissionRequest, QuizSubmissionResponse
from models.quiz_job_models import QuizStatusResponse, QuizJobListItem
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/quiz/{quiz_job_id}")
def get_quiz_status(quiz_job_id: str, x_user_id: str = Header(...)) -> QuizStatusResponse:
    """Poll status of quiz generation job."""
    try:
        status_response = quiz_job_service.get_job_status_response(quiz_job_id, x_user_id)

        if not status_response:
            raise HTTPException(status_code=404, detail=f"Quiz job '{quiz_job_id}' not found")

        return status_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz status for job {quiz_job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz status")


@router.post("/quiz/{quiz_job_id}/submit")
def submit_quiz_answers(quiz_job_id: str, submission: QuizSubmissionRequest, x_user_id: str = Header(...)) -> QuizSubmissionResponse:
    """Submit quiz answers and get detailed results."""
    try:
        response = quiz_job_service.submit_quiz_answers(quiz_job_id, x_user_id, submission)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting quiz answers for job {quiz_job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process quiz submission")


@router.get("/quizzes")
def list_user_quiz_jobs(
    x_user_id: str = Header(...),
    limit: int = Query(20, ge=1, le=100, description="Number of quiz jobs to retrieve")
) -> ApiResponseWithBody:
    """List all quiz jobs for a user with quiz_job_id and title."""
    try:
        quiz_jobs = quiz_job_service.get_user_quiz_jobs(x_user_id, limit)

        return ApiResponseWithBody(
            status="SUCCESS",
            message=f"Found {len(quiz_jobs)} quiz jobs",
            body={"quizzes": quiz_jobs}
        )
    except Exception as e:
        logger.error(f"Error listing quiz jobs for user {x_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz jobs")


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: str, x_user_id: str = Header(...)) -> ApiResponseWithBody:
    """Get a specific quiz by ID."""
    try:
        quiz = quiz_repository.get_quiz_by_id(x_user_id, quiz_id)

        if not quiz:
            raise HTTPException(status_code=404, detail=f"Quiz '{quiz_id}' not found")

        # Reconstruct QuizResponse format
        quiz_response_data = {
            "quiz_data": quiz["quiz_data"],
            "generation_metadata": quiz["generation_metadata"]
        }

        return ApiResponseWithBody(
            status="SUCCESS",
            message="Quiz retrieved successfully",
            body={"quiz": quiz_response_data}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving quiz {quiz_id} for user {x_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz")


@router.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: str, x_user_id: str = Header(...)) -> ApiResponse:
    """Delete a specific quiz."""
    try:
        success = quiz_repository.delete_quiz(x_user_id, quiz_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Quiz '{quiz_id}' not found")

        return ApiResponse(
            status="SUCCESS",
            message=f"Quiz '{quiz_id}' deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quiz {quiz_id} for user {x_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete quiz")


@router.get("/collections/{collection_name}/quizzes")
def get_collection_quizzes(
    collection_name: str,
    x_user_id: str = Header(...)
) -> ApiResponseWithBody:
    """Get all quizzes for a specific collection."""
    try:
        quizzes = quiz_repository.get_collection_quizzes(x_user_id, collection_name)

        return ApiResponseWithBody(
            status="SUCCESS",
            message=f"Found {len(quizzes)} quizzes for collection '{collection_name}'",
            body={"quizzes": quizzes}
        )
    except Exception as e:
        logger.error(f"Error retrieving quizzes for collection {collection_name} and user {x_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve collection quizzes")


@router.get("/quizzes/{quiz_id}/exists")
def check_quiz_exists(quiz_id: str, x_user_id: str = Header(...)) -> ApiResponse:
    """Check if a quiz exists."""
    try:
        exists = quiz_repository.quiz_exists(x_user_id, quiz_id)

        if exists:
            return ApiResponse(
                status="SUCCESS",
                message=f"Quiz '{quiz_id}' exists"
            )
        else:
            return ApiResponse(
                status="FAILURE",
                message=f"Quiz '{quiz_id}' does not exist"
            )
    except Exception as e:
        logger.error(f"Error checking if quiz {quiz_id} exists for user {x_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to check quiz existence")