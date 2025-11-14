from datetime import datetime
from models.api_models import LinkContentItem, LinkContentResponse, UnlinkContentResponse
from models.quiz_models import QuizResponse, QuizData, QuizMetadata, QuizSource, ContentSummary, ScoringInfo, GenerationMetadata
from models.api_models import QueryResponse
import time

class ResponseBuilder:
    @staticmethod
    def link_success(file_item: LinkContentItem) -> LinkContentResponse:
        return LinkContentResponse(
            name=file_item.name,
            file_id=file_item.file_id,
            type=file_item.type,
            created_at=datetime.now().isoformat(),
            indexing_status="INDEXING_SUCCESS",
            status_code=200,
            message="Successfully linked to collection"
        )

    @staticmethod
    def link_error(file_item: LinkContentItem, status_code: int, message: str) -> LinkContentResponse:
        return LinkContentResponse(
            name=file_item.name,
            file_id=file_item.file_id,
            type=file_item.type,
            created_at=None,
            indexing_status="INDEXING_FAILED",
            status_code=status_code,
            message=message
        )

    @staticmethod
    def unlink_response(file_id: str, status_code: int, message: str) -> UnlinkContentResponse:
        return UnlinkContentResponse(
            file_id=file_id,
            status_code=status_code,
            message=message
        )

    @staticmethod
    def query_error(message: str) -> QueryResponse:
        return QueryResponse(
            answer=message,
            confidence=0.0,
            is_relevant=False,
            chunks=[]
        )

    @staticmethod
    def quiz_error(message: str, collection_name: str) -> QuizResponse:
        quiz_metadata = QuizMetadata(
            quiz_id="error",
            title="Quiz Generation Error",
            difficulty="unknown",
            estimated_time_minutes=0,
            total_questions=0,
            max_score=0,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            source=QuizSource(type="collection", collection_name=collection_name, source_count=0)
        )

        return QuizResponse(
            quiz_data=QuizData(
                quiz_metadata=quiz_metadata,
                questions=[],
                content_summary=ContentSummary(
                    main_summary=message,
                    key_concepts=[],
                    topics_covered=[],
                    prerequisite_knowledge=[]
                ),
                scoring_info=ScoringInfo(
                    total_score=0,
                    passing_score=0,
                    time_limit_minutes=0
                )
            ),
            generation_metadata=GenerationMetadata(
                confidence=0.0,
                is_relevant=False,
                generation_time_ms=0,
                model_used="unknown",
                content_sources=[]
            )
        )