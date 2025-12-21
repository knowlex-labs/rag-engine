import logging
from typing import List
from fastapi import APIRouter, Header
from pydantic import BaseModel

from services.legal_query import LegalQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/law", tags=["Legal Assistant"])

class LegalQueryRequest(BaseModel):
    question: str
    scope: List[str] = []  # Optional filtering: ["constitution", "bns", "all"] or empty for all

class LegalQueryResponse(BaseModel):
    answer: str
    question: str
    sources: list
    total_chunks_found: int
    chunks_used: int

legal_service = LegalQueryService()

@router.post("/chat", response_model=LegalQueryResponse)
async def legal_assistant_chat(
    request: LegalQueryRequest,
    x_user_id: str = Header(...)
):
    logger.info(f"Legal assistant query from user {x_user_id}: {request.question}")

    result = await legal_service.process_legal_query(
        request,
        x_user_id
    )

    return LegalQueryResponse(**result)