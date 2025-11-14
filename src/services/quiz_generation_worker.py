import logging
from services.quiz_job_service import quiz_job_service
from services.query_service import QueryService
from repositories.quiz_repository import quiz_repository
from models.quiz_job_models import GenerationStatus
from models.quiz_models import QuizResponse

logger = logging.getLogger(__name__)


class QuizGenerationWorker:
    def __init__(self):
        self.query_service = QueryService()

    def generate_quiz_async(self, quiz_job_id: str):
        """Background task to generate quiz and update job status."""

        try:
            # Get job details
            job = quiz_job_service.get_job_status(quiz_job_id)
            if not job:
                logger.error(f"Quiz job {quiz_job_id} not found")
                return

            # Update status to generating
            quiz_job_service.update_job_status(quiz_job_id, GenerationStatus.GENERATING, 10)

            job_metadata = job.job_metadata

            # Get qdrant collection name (same logic as collection service)
            qdrant_collection_name = f"{job_metadata.user_id}_{job_metadata.collection_name}"

            # Update progress
            quiz_job_service.update_job_status(quiz_job_id, GenerationStatus.GENERATING, 30)

            # Generate the quiz using existing query service
            result = self.query_service.search(
                collection_name=qdrant_collection_name,
                query_text=job_metadata.query_text,
                limit=10,
                enable_critic=True,
                structured_output=False,
                quiz_config=job_metadata.quiz_config
            )

            # Update progress
            quiz_job_service.update_job_status(quiz_job_id, GenerationStatus.GENERATING, 80)

            # Check if quiz generation was successful
            if isinstance(result, QuizResponse) and result.quiz_data.questions:
                # Save to database
                try:
                    quiz_repository.save_quiz(job_metadata.user_id, result)
                    logger.info(f"Quiz '{result.quiz_data.quiz_metadata.quiz_id}' saved for user '{job_metadata.user_id}'")
                except Exception as e:
                    logger.error(f"Failed to save quiz to database: {e}")
                    # Continue with job completion even if saving fails

                # Complete the job
                quiz_job_service.complete_job(quiz_job_id, result)
                logger.info(f"Quiz generation completed for job {quiz_job_id}")

            else:
                # Quiz generation failed
                error_msg = "Failed to generate quiz questions"
                if hasattr(result, 'quiz_data') and hasattr(result.quiz_data, 'content_summary'):
                    error_msg = result.quiz_data.content_summary.main_summary

                quiz_job_service.fail_job(quiz_job_id, error_msg)
                logger.error(f"Quiz generation failed for job {quiz_job_id}: {error_msg}")

        except Exception as e:
            error_message = f"Quiz generation error: {str(e)}"
            quiz_job_service.fail_job(quiz_job_id, error_message)
            logger.error(f"Quiz generation worker failed for job {quiz_job_id}: {e}")


# Global instance
quiz_generation_worker = QuizGenerationWorker()