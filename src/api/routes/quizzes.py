from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Optional, Dict, Any
from models.api_models import ApiResponse, ApiResponseWithBody
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
    """
    List active/recent quiz jobs for a user.
    Note: Only lists jobs currently in memory (server session).
    """
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