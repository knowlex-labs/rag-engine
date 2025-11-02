from fastapi import APIRouter
from models.api_models import FeedbackRequest, FeedbackResponse
from services.feedback_service import FeedbackService

router = APIRouter()
feedback_service = FeedbackService()

@router.post("/feedback")
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    success = feedback_service.save_feedback(
        query=request.query,
        doc_ids=request.doc_ids,
        label=request.label,
        collection=request.collection
    )

    if success:
        return FeedbackResponse(
            status="SUCCESS",
            message="Feedback saved successfully"
        )
    else:
        return FeedbackResponse(
            status="FAILURE",
            message="Failed to save feedback"
        )