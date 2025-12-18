from datetime import datetime
from models.api_models import LinkContentItem, LinkContentResponse, UnlinkContentResponse
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