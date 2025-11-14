import uuid
import logging
from typing import Dict, Optional, List
from datetime import datetime
from models.quiz_job_models import (
    QuizJobStatus, QuizJobMetadata, GenerationStatus,
    QuizJobResponse, QuizStatusResponse, QuizJobListItem
)
from models.api_models import QuizConfig
from models.quiz_models import QuizResponse, QuizSubmissionRequest, QuizSubmissionResponse, AnswerResult
from repositories.quiz_repository import quiz_repository

logger = logging.getLogger(__name__)


class QuizJobService:
    def __init__(self):
        # In-memory job storage - could be upgraded to Redis later
        self._jobs: Dict[str, QuizJobStatus] = {}

    def create_quiz_job(
        self,
        user_id: str,
        collection_name: str,
        query_text: str,
        quiz_config: QuizConfig
    ) -> QuizJobResponse:
        """Create a new quiz generation job and return job ID."""

        quiz_job_id = f"qjob_{uuid.uuid4().hex[:8]}"

        job_metadata = QuizJobMetadata(
            user_id=user_id,
            collection_name=collection_name,
            query_text=query_text,
            quiz_config=quiz_config,
            created_at=datetime.utcnow()
        )

        job_status = QuizJobStatus(
            quiz_job_id=quiz_job_id,
            generation_status=GenerationStatus.PENDING,
            job_metadata=job_metadata,
            progress_percent=0,
            updated_at=datetime.utcnow()
        )

        self._jobs[quiz_job_id] = job_status

        logger.info(f"Created quiz job {quiz_job_id} for user {user_id}")

        return QuizJobResponse(
            quiz_job_id=quiz_job_id,
            status="OK",
            message="Quiz generation started"
        )

    def get_job_status(self, quiz_job_id: str) -> Optional[QuizJobStatus]:
        """Get the current status of a quiz job."""
        return self._jobs.get(quiz_job_id)

    def update_job_status(
        self,
        quiz_job_id: str,
        status: GenerationStatus,
        progress_percent: int = None,
        error_message: str = None
    ) -> bool:
        """Update the status of a quiz job."""

        if quiz_job_id not in self._jobs:
            return False

        job = self._jobs[quiz_job_id]
        job.generation_status = status
        job.updated_at = datetime.utcnow()

        if progress_percent is not None:
            job.progress_percent = progress_percent

        if error_message is not None:
            job.error_message = error_message

        logger.info(f"Updated job {quiz_job_id} status to {status}")
        return True

    def complete_job(self, quiz_job_id: str, quiz_result: QuizResponse) -> bool:
        """Mark a job as completed with the quiz result."""

        if quiz_job_id not in self._jobs:
            return False

        job = self._jobs[quiz_job_id]
        job.generation_status = GenerationStatus.COMPLETED
        job.quiz_result = quiz_result
        job.quiz_id = quiz_result.quiz_data.quiz_metadata.quiz_id  # Store quiz_id for fallback
        job.progress_percent = 100
        job.updated_at = datetime.utcnow()

        logger.info(f"Completed quiz job {quiz_job_id} (quiz_id: {job.quiz_id})")
        return True

    def fail_job(self, quiz_job_id: str, error_message: str) -> bool:
        """Mark a job as failed with error message."""

        if quiz_job_id not in self._jobs:
            return False

        job = self._jobs[quiz_job_id]
        job.generation_status = GenerationStatus.FAILED
        job.error_message = error_message
        job.updated_at = datetime.utcnow()

        logger.error(f"Failed quiz job {quiz_job_id}: {error_message}")
        return True

    def get_job_status_response(self, quiz_job_id: str, user_id: str) -> Optional[QuizStatusResponse]:
        """Get a formatted status response for the API."""

        job = self._jobs.get(quiz_job_id)
        if not job:
            # Try fallback from database
            return self._try_fallback_from_database(quiz_job_id, user_id)

        # Check if user owns this job
        if job.job_metadata.user_id != user_id:
            return None

        response = QuizStatusResponse(
            quiz_job_id=quiz_job_id,
            generation_status=job.generation_status,
            progress_percent=job.progress_percent,
            created_at=job.job_metadata.created_at.isoformat() + "Z"
        )

        if job.generation_status == GenerationStatus.COMPLETED and job.quiz_result:
            response.quiz_data = job.quiz_result.dict()
        elif job.generation_status == GenerationStatus.FAILED:
            response.error_message = job.error_message

        return response

    def cleanup_old_jobs(self, hours_old: int = 24) -> int:
        """Remove jobs older than specified hours. Returns count of removed jobs."""

        cutoff_time = datetime.utcnow().timestamp() - (hours_old * 3600)
        old_job_ids = []

        for job_id, job in self._jobs.items():
            if job.job_metadata.created_at.timestamp() < cutoff_time:
                old_job_ids.append(job_id)

        for job_id in old_job_ids:
            del self._jobs[job_id]

        if old_job_ids:
            logger.info(f"Cleaned up {len(old_job_ids)} old quiz jobs")

        return len(old_job_ids)

    def _try_fallback_from_database(self, quiz_job_id: str, user_id: str) -> Optional[QuizStatusResponse]:
        """Try to provide helpful response when job not found in memory."""
        try:
            # Quiz jobs are stored in memory only, so when memory clears (server restart),
            # the job data is lost but quiz data persists in database
            logger.info(f"Quiz job {quiz_job_id} not found in memory (likely server restart). Quiz data may still exist in database.")

            # Return a helpful response indicating the job is no longer trackable
            # but quiz data might exist in saved quizzes
            response = QuizStatusResponse(
                quiz_job_id=quiz_job_id,
                generation_status=GenerationStatus.COMPLETED,  # Assume completed since job existed
                progress_percent=100,
                created_at=datetime.utcnow().isoformat() + "Z",
                error_message="Job no longer trackable. Check /quizzes endpoint for saved quizzes."
            )
            return response
        except Exception as e:
            logger.error(f"Failed to create fallback response: {e}")
            return None

    def get_user_quiz_jobs(self, user_id: str, limit: int = 20) -> List[QuizJobListItem]:
        """Get quiz jobs list for a user with quiz_job_id and title."""

        user_jobs = []
        for job in self._jobs.values():
            if job.job_metadata.user_id == user_id:
                # Create title from collection name and difficulty
                collection_display = job.job_metadata.collection_name.replace('_', ' ').title()
                title = f"{collection_display} Quiz - {job.job_metadata.quiz_config.difficulty.title()}"

                quiz_job_item = QuizJobListItem(
                    quiz_job_id=job.quiz_job_id,
                    title=title,
                    generation_status=job.generation_status,
                    collection_name=job.job_metadata.collection_name,
                    difficulty=job.job_metadata.quiz_config.difficulty,
                    created_at=job.job_metadata.created_at.isoformat() + "Z"
                )
                user_jobs.append(quiz_job_item)

        # Sort by creation time, most recent first
        user_jobs.sort(key=lambda x: x.created_at, reverse=True)
        return user_jobs[:limit]

    def submit_quiz_answers(self, quiz_job_id: str, user_id: str, submission: QuizSubmissionRequest) -> QuizSubmissionResponse:
        """Process quiz submission and return detailed results."""

        # Get the quiz job
        job = self._jobs.get(quiz_job_id)
        if not job:
            raise ValueError(f"Quiz job '{quiz_job_id}' not found")

        # Check user ownership
        if job.job_metadata.user_id != user_id:
            raise ValueError("Access denied: Quiz job belongs to different user")

        # Check if quiz is completed
        if job.generation_status != GenerationStatus.COMPLETED:
            raise ValueError(f"Quiz is not ready for submission. Status: {job.generation_status}")

        # Check if quiz result exists
        if not job.quiz_result:
            raise ValueError("Quiz result not found")

        # Extract quiz data
        quiz_data = job.quiz_result.quiz_data
        questions = quiz_data.questions

        # Process answers
        answer_results = []
        total_score = 0
        max_score = 0
        correct_count = 0
        total_questions = len(questions)

        for question in questions:
            question_id = question.question_id
            correct_answer = question.answer_config.correct_answer
            max_points = question.answer_config.max_score
            max_score += max_points

            # Get submitted answer (default to empty if not provided)
            submitted_answer = submission.answers.get(question_id, "")

            # Check if correct
            is_correct = submitted_answer == correct_answer
            points_earned = max_points if is_correct else 0
            total_score += points_earned

            if is_correct:
                correct_count += 1

            # Create answer result
            answer_result = AnswerResult(
                question_id=question_id,
                submitted_answer=submitted_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                points_earned=points_earned,
                max_points=max_points,
                question_text=question.question_config.question_text
            )
            answer_results.append(answer_result)

        # Calculate percentage and pass/fail
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        passing_score = quiz_data.scoring_info.passing_score
        passed = total_score >= passing_score

        # Create summary
        summary = {
            "correct": correct_count,
            "incorrect": total_questions - correct_count,
            "total": total_questions
        }

        # Create response
        response = QuizSubmissionResponse(
            quiz_job_id=quiz_job_id,
            total_score=total_score,
            max_score=max_score,
            percentage=round(percentage, 1),
            passed=passed,
            time_taken_seconds=submission.time_taken_seconds,
            submitted_at=submission.submitted_at,
            answer_results=answer_results,
            summary=summary
        )

        logger.info(f"Quiz submission processed for job {quiz_job_id}: {correct_count}/{total_questions} correct")
        return response


# Global instance
quiz_job_service = QuizJobService()