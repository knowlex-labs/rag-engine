import logging
from fastapi import APIRouter, Header
from pydantic import BaseModel

from services.legal_query import LegalQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/law", tags=["Legal Assistant"])

class LegalQueryRequest(BaseModel):
    question: str

class LegalQueryResponse(BaseModel):
    answer: str
    sources: list
    total_chunks: int

legal_service = LegalQueryService()

@router.post("/chat", response_model=LegalQueryResponse)
def legal_assistant_chat(
    request: LegalQueryRequest,
    x_user_id: str = Header(...)
):
    logger.info(f"Legal assistant query from user {x_user_id}: {request.question}")

    result = legal_service.query_constitutional_law(
        request.question,
        x_user_id
    )

    return LegalQueryResponse(**result)