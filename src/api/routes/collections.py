from fastapi import APIRouter, HTTPException, Response, Query, Header, BackgroundTasks
from typing import List, Optional, Union
from api.api_constants import *
from models.api_models import LinkContentItem, LinkContentResponse, QueryRequest, QueryResponse, UnlinkContentResponse, ApiResponse
from models.quiz_models import QuizResponse
from models.quiz_job_models import QuizJobResponse
from services.collection_service import CollectionService

router = APIRouter()
collection_service = CollectionService()

@router.post("/{collection_name}" + LINK_CONTENT)
def link_content(collection_name: str, files: List[LinkContentItem], response: Response, x_user_id: str = Header(...)) -> List[LinkContentResponse]:
    """
    Ingest text, files, or URLs into a logical collection.
    Parses content and stores it in the user's vector store with collection_id=collection_name.
    """
    response.status_code = 207
    return collection_service.link_content(collection_name, files, x_user_id)

@router.post("/{collection_name}" + UNLINK_CONTENT)
def unlink_content(collection_name: str, file_ids: List[str], response: Response, x_user_id: str = Header(...)) -> List[UnlinkContentResponse]:
    """
    Remove content from a logical collection.
    Deletes vectors matching collection_id=collection_name AND file_id IN file_ids.
    """
    response.status_code = 207
    return collection_service.unlink_content(collection_name, file_ids, x_user_id)

@router.post("/{collection_name}" + QUERY_COLLECTION)
def query_collection(collection_name: str, request: QueryRequest, background_tasks: BackgroundTasks, x_user_id: str = Header(...)) -> Union[QueryResponse, QuizResponse, QuizJobResponse]:
    """
    Query the vector store, filtering by the logical collection name.
    """
    return collection_service.query_collection(
        x_user_id,
        collection_name,
        request.query,
        request.enable_critic,
        request.structured_output,
        request.quiz_config,
        background_tasks
    )

@router.post("/purge")
def purge_user_data(x_user_id: str = Header(...)) -> ApiResponse:
    """
    Delete ALL vector data for the user.
    """
    success = collection_service.purge_user_data(x_user_id)
    if success:
        return ApiResponse(status="success", message="User data purged successfully")
    else:
        return ApiResponse(status="error", message="Failed to purge data (or no data found)")
