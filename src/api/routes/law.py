"""
Consolidated Law API Routes
Simplified and unified endpoints for all legal functionality.
"""

import logging
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from typing import Optional, List, Dict, Any

# Import all the models needed
from models.question_models import (
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    SimpleQuestionGenerationRequest,
    DifficultyLevel,
    QuestionType,
    QuestionRequest,
    QuestionFilters
)
from models.law_query_models import (
    LawQueryRequest,
    LawQueryResponse,
    BatchLawQueryRequest,
    BatchLawQueryResponse
)
from models.law_summary_models import (
    LegalSummaryRequest,
    LegalSummaryResponse,
    BatchSummaryRequest,
    BatchSummaryResponse
)
from models.api_models import RetrieveRequest, RetrieveResponse

# Import services
from services.enhanced_question_generator import enhanced_question_generator
from services.legal_query import LegalQueryService
from services.law_summary_service import LegalSummaryService
from services.query_service import QueryService

# Initialize router and services
router = APIRouter()
legal_query_service = LegalQueryService()
legal_summary_service = LegalSummaryService()
query_service = QueryService()
logger = logging.getLogger(__name__)


# =============================================================================
# LEGAL ASSISTANT / CHAT
# =============================================================================

class LegalChatRequest:
    def __init__(self, question: str, scope: List[str] = None):
        self.question = question
        self.scope = scope or []

class LegalChatResponse:
    def __init__(self, **kwargs):
        self.answer = kwargs.get('answer', '')
        self.question = kwargs.get('question', '')
        self.sources = kwargs.get('sources', [])
        self.total_chunks_found = kwargs.get('total_chunks_found', 0)
        self.chunks_used = kwargs.get('chunks_used', 0)
        self.documents_searched = kwargs.get('documents_searched', [])
        self.processing_time_ms = kwargs.get('processing_time_ms', 0)

@router.post("/chat")
async def legal_assistant_chat(
    request: dict,
    x_user_id: str = Header(...)
):
    """
    Interactive legal assistant chat for constitutional and BNS questions.

    Supports both simple question-answer format and advanced legal queries.
    """
    try:
        logger.info(f"Legal assistant query from user {x_user_id}: {request.get('question', '')}")

        # Create request object from dict
        chat_request = LegalChatRequest(
            question=request.get('question', ''),
            scope=request.get('scope', [])
        )

        result = await legal_query_service.process_legal_query(
            chat_request,
            x_user_id
        )

        return LegalChatResponse(**result).__dict__

    except Exception as e:
        logger.error(f"Legal chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Legal chat failed: {str(e)}")


# =============================================================================
# LEGAL QUERY / SEARCH
# =============================================================================

@router.post("/query", response_model=LawQueryResponse)
async def query_legal_document(
    request: LawQueryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> LawQueryResponse:
    """
    Query Indian legal documents (Constitution, BNS) with intelligent context retrieval.

    **Features:**
    - Constitutional question answering with article references
    - Multi-document search (Constitution + BNS)
    - Customizable answer styles for different audiences
    - Source attribution with relevance scoring
    - Related legal concepts extraction

    **Example Queries:**
    - "What are fundamental rights under Article 19?"
    - "Explain the emergency provisions in the Constitution"
    - "What is the difference between Article 14 and Article 15?"
    """
    try:
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        start_time = time.time()
        response = await legal_query_service.process_legal_query(
            request=request,
            user_id=x_user_id
        )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Legal query processed in {processing_time}ms: {request.question[:50]}...")

        return response

    except ValueError as e:
        logger.warning(f"Invalid request parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing legal query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while processing legal query")


@router.post("/query/batch", response_model=BatchLawQueryResponse)
async def batch_query_legal_documents(
    request: BatchLawQueryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> BatchLawQueryResponse:
    """
    Process multiple legal queries in a single batch request.

    Useful for processing multiple related questions efficiently.
    """
    try:
        if not request.queries or len(request.queries) == 0:
            raise HTTPException(status_code=400, detail="At least one query is required")

        if len(request.queries) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 queries per batch request")

        start_time = time.time()

        results = []
        for query_req in request.queries:
            try:
                result = await legal_query_service.process_legal_query(
                    request=query_req,
                    user_id=x_user_id
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing query in batch: {e}")
                # Add error response for failed query
                results.append(LawQueryResponse(
                    answer="Error processing this query",
                    question=query_req.question,
                    sources=[],
                    success=False,
                    error_message=str(e)
                ))

        processing_time = int((time.time() - start_time) * 1000)

        return BatchLawQueryResponse(
            responses=results,
            total_queries=len(request.queries),
            successful_queries=sum(1 for r in results if getattr(r, 'success', True)),
            failed_queries=sum(1 for r in results if not getattr(r, 'success', True)),
            processing_time_ms=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch query processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch processing")


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_legal_content(
    request: RetrieveRequest,
    x_user_id: str = Header(..., description="User ID for context isolation")
) -> RetrieveResponse:
    """
    Retrieve relevant legal content without generating answers.

    Returns raw context chunks for further processing.
    """
    try:
        response = await query_service.retrieve_context(
            request=request,
            user_id=x_user_id
        )
        return response

    except Exception as e:
        logger.error(f"Content retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Content retrieval failed: {str(e)}")


# =============================================================================
# LEGAL SUMMARIES
# =============================================================================

@router.post("/summary", response_model=LegalSummaryResponse)
async def generate_legal_summary(
    request: LegalSummaryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation"),
    background_tasks: BackgroundTasks = None
) -> LegalSummaryResponse:
    """
    Generate intelligent constitutional law summaries with customizable focus and formatting.

    **Features:**
    - Smart content selection from constitutional provisions
    - Audience customization (students, professionals, exam aspirants)
    - Multiple formats (bullet points, paragraphs, outlines, tables)
    - Focus areas (key provisions, cases, amendments, applications)

    **Summary Types:**
    - Bullet Points: Structured, easy-to-scan format
    - Paragraph: Flowing narrative format
    - Outline: Hierarchical organization
    - Table: Comparative tabular format
    """
    try:
        if not request.topic.strip():
            raise HTTPException(status_code=400, detail="Topic cannot be empty")

        if request.target_words < 100 or request.target_words > 2000:
            raise HTTPException(
                status_code=400,
                detail="Target words must be between 100 and 2000"
            )

        start_time = time.time()
        response = await legal_summary_service.generate_summary(
            request=request,
            user_id=x_user_id
        )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Legal summary generated in {processing_time}ms: {request.topic[:50]}...")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during summary generation")


@router.post("/summary/batch", response_model=BatchSummaryResponse)
async def generate_batch_summaries(
    request: BatchSummaryRequest,
    x_user_id: str = Header(..., description="User ID for context isolation"),
    background_tasks: BackgroundTasks = None
) -> BatchSummaryResponse:
    """
    Generate multiple legal summaries in a single batch request.

    Efficient processing of multiple related topics.
    """
    try:
        if not request.requests or len(request.requests) == 0:
            raise HTTPException(status_code=400, detail="At least one summary request is required")

        if len(request.requests) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 summary requests per batch")

        start_time = time.time()

        results = []
        for summary_req in request.requests:
            try:
                result = await legal_summary_service.generate_summary(
                    request=summary_req,
                    user_id=x_user_id
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error generating summary in batch: {e}")
                # Add error response for failed summary
                results.append(LegalSummaryResponse(
                    topic=summary_req.topic,
                    summary="Error generating this summary",
                    success=False,
                    error_message=str(e)
                ))

        processing_time = int((time.time() - start_time) * 1000)

        return BatchSummaryResponse(
            responses=results,
            total_requests=len(request.requests),
            successful_requests=sum(1 for r in results if getattr(r, 'success', True)),
            failed_requests=sum(1 for r in results if not getattr(r, 'success', True)),
            processing_time_ms=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch summary generation")


# =============================================================================
# QUESTION GENERATION / QUIZ
# =============================================================================

@router.post("/questions", response_model=QuestionGenerationResponse)
async def generate_questions(
    request: SimpleQuestionGenerationRequest,
    background_tasks: BackgroundTasks
) -> QuestionGenerationResponse:
    """
    Generate legal exam questions using simplified format.

    **Request Format:**
    ```json
    {
        "title": "Quiz for BNS acts",
        "scope": ["bns"],
        "num_questions": 10,
        "difficulty": "easy",
        "question_data": [
            {"question_type": "Assertion_reason", "num_questions": 5},
            {"question_type": "MCQ", "num_questions": 5}
        ]
    }
    ```

    **Question Types:**
    - "Assertion_reason": Assertion-reasoning format
    - "MCQ": Multiple choice questions
    - "Match the following": Match items format
    - "Comprehension": Passage-based questions

    **Scope Options:**
    - ["bns"]: BNS questions only
    - ["constitution"]: Constitution questions only
    - ["bns", "constitution"]: Mixed questions

    **Difficulty Levels:** "easy", "medium", "hard"
    """
    try:
        logger.info(f"Question generation request: {request.title}, {request.num_questions} questions, scope: {request.scope}")

        # Map scope to collection IDs
        collection_ids = []
        for scope in request.scope:
            if scope == "bns":
                collection_ids.append("bns-golden-source")
            elif scope == "constitution":
                collection_ids.append("constitution-golden-source")

        if not collection_ids:
            raise HTTPException(status_code=400, detail="Invalid scope. Use 'bns' and/or 'constitution'")

        # Map difficulty
        difficulty_map = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MODERATE,
            "hard": DifficultyLevel.DIFFICULT
        }
        internal_difficulty = difficulty_map[request.difficulty]

        # Map question types
        question_type_map = {
            "assertion_reason": QuestionType.ASSERTION_REASONING,
            "mcq": QuestionType.MCQ,
            "match the following": QuestionType.MATCH_FOLLOWING,
            "comprehension": QuestionType.COMPREHENSION
        }

        internal_questions = []
        for q_data in request.question_data:
            q_type_key = q_data.question_type.lower()
            if q_type_key not in question_type_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported question type: {q_data.question_type}. Use: 'Assertion_reason', 'MCQ', 'Match the following', 'Comprehension'"
                )

            internal_questions.append(QuestionRequest(
                type=question_type_map[q_type_key],
                count=q_data.num_questions,
                difficulty=internal_difficulty,
                filters=QuestionFilters(collection_ids=collection_ids)
            ))

        # Create internal request format
        internal_request = QuestionGenerationRequest(questions=internal_questions)

        # Generate questions
        response = await enhanced_question_generator.generate_questions(internal_request)

        logger.info(f"Generated {response.total_generated}/{request.num_questions} questions successfully")

        # Add background task for analytics if needed
        if response.success:
            background_tasks.add_task(_log_generation_analytics, request, response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Question generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(e)}")


@router.post("/questions/batch", response_model=List[QuestionGenerationResponse])
async def batch_generate_questions(
    requests: List[SimpleQuestionGenerationRequest],
    background_tasks: BackgroundTasks
) -> List[QuestionGenerationResponse]:
    """
    Generate multiple question sets in a single batch request.

    Useful for creating multiple quizzes efficiently.
    """
    try:
        if not requests or len(requests) == 0:
            raise HTTPException(status_code=400, detail="At least one question generation request is required")

        if len(requests) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 question generation requests per batch")

        results = []
        for request in requests:
            try:
                response = await generate_questions(request, background_tasks)
                results.append(response)
            except Exception as e:
                logger.error(f"Error generating questions in batch: {e}")
                # Add error response
                results.append(QuestionGenerationResponse(
                    success=False,
                    total_generated=0,
                    questions=[],
                    errors=[str(e)]
                ))

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch question generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch question generation")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _log_generation_analytics(request: SimpleQuestionGenerationRequest, response: QuestionGenerationResponse):
    """Background task to log question generation analytics"""
    try:
        analytics_data = {
            "timestamp": datetime.now().isoformat(),
            "request_summary": {
                "title": request.title,
                "total_requested": request.num_questions,
                "scope": request.scope,
                "difficulty": request.difficulty,
                "question_types": [q.question_type for q in request.question_data]
            },
            "response_summary": {
                "success": response.success,
                "total_generated": response.total_generated,
                "error_count": len(response.errors) if hasattr(response, 'errors') else 0
            }
        }
        logger.info(f"Question generation analytics: {analytics_data}")
    except Exception as e:
        logger.error(f"Failed to log analytics: {e}")