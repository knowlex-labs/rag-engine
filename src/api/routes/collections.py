from fastapi import APIRouter, HTTPException, Response, Query, Header, BackgroundTasks
from typing import List, Optional, Union
from api.api_constants import *
from models.api_models import CreateCollectionRequest, ApiResponse, ApiResponseWithBody, LinkContentItem, LinkContentResponse, QueryRequest, QueryResponse, UnlinkContentResponse, GetEmbeddingsResponse
from models.quiz_models import QuizResponse
from models.quiz_job_models import QuizJobResponse
from services.collection_service import CollectionService

router = APIRouter()
collection_service = CollectionService()

@router.get("/collections")
def list_collections(x_user_id: str = Header(...)) -> ApiResponseWithBody:
    return collection_service.list_collections(x_user_id)

@router.get(COLLECTIONS_BASE + "/{collection_name}")
def get_collection(collection_name: str, x_user_id: str = Header(...)) -> ApiResponse:
    return collection_service.get_collection(x_user_id, collection_name)

@router.post(COLLECTIONS_BASE)
def create_collection(request: CreateCollectionRequest, x_user_id: str = Header(...)) -> ApiResponse:
    return collection_service.create_collection(
        x_user_id,
        request.name,
        request.rag_config.dict() if request.rag_config else None,
        request.indexing_config.dict() if request.indexing_config else None
    )

@router.delete(COLLECTIONS_BASE + "/{collection_name}")
def delete_collection(collection_name: str, x_user_id: str = Header(...)) -> ApiResponse:
    return collection_service.delete_collection(x_user_id, collection_name)


@router.post("/{collection_name}" + LINK_CONTENT)
def link_content(collection_name: str, files: List[LinkContentItem], response: Response, x_user_id: str = Header(...)) -> List[LinkContentResponse]:
    response.status_code = 207
    return collection_service.link_content(collection_name, files, x_user_id)

@router.post("/{collection_name}" + UNLINK_CONTENT)
def unlink_content(collection_name: str, file_ids: List[str], response: Response, x_user_id: str = Header(...)) -> List[UnlinkContentResponse]:
    response.status_code = 207
    return collection_service.unlink_content(collection_name, file_ids, x_user_id)

@router.post("/{collection_name}" + QUERY_COLLECTION)
def query_collection(collection_name: str, request: QueryRequest, background_tasks: BackgroundTasks, x_user_id: str = Header(...)) -> Union[QueryResponse, QuizResponse, QuizJobResponse]:
    return collection_service.query_collection(
        x_user_id,
        collection_name,
        request.query,
        request.enable_critic,
        request.structured_output,
        request.quiz_config,
        background_tasks
    )

@router.get("/{collection_name}/embeddings")
def get_collection_embeddings(
    collection_name: str,
    x_user_id: str = Header(...),
    limit: int = Query(100, ge=1, le=500, description="Number of embeddings to retrieve per page"),
    offset: Optional[str] = Query(None, description="Pagination offset token"),
    include_vectors: bool = Query(False, description="Include vector data in response")
) -> GetEmbeddingsResponse:
    result = collection_service.get_collection_embeddings(
        user_id=x_user_id,
        collection_name=collection_name,
        limit=limit,
        offset=offset,
        include_vectors=include_vectors
    )

    return GetEmbeddingsResponse(
        status=result["status"],
        message=result["message"],
        body=result["body"]
    )

