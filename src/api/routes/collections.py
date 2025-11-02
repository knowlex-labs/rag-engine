from fastapi import APIRouter, HTTPException, Response
from typing import List
from api.api_constants import *
from models.api_models import CreateCollectionRequest, ApiResponse, ApiResponseWithBody, LinkContentItem, LinkContentResponse, QueryRequest, QueryResponse, UnlinkContentResponse
from services.collection_service import CollectionService

router = APIRouter()
collection_service = CollectionService()

@router.get("/collections")
def list_collections() -> ApiResponseWithBody:
    return collection_service.list_collections()

@router.get(COLLECTIONS_BASE + "/{collection_name}")
def get_collection(collection_name: str) -> ApiResponse:
    return collection_service.get_collection(collection_name)

@router.post(COLLECTIONS_BASE)
def create_collection(request: CreateCollectionRequest) -> ApiResponse:
    return collection_service.create_collection(
        request.name,
        request.rag_config.dict() if request.rag_config else None,
        request.indexing_config.dict() if request.indexing_config else None
    )

@router.delete(COLLECTIONS_BASE + "/{collection_name}")
def delete_collection(collection_name: str) -> ApiResponse:
    return collection_service.delete_collection(collection_name)


@router.post("/{collection_name}" + LINK_CONTENT)
def link_content(collection_name: str, files: List[LinkContentItem], response: Response) -> List[LinkContentResponse]:
    response.status_code = 207
    return collection_service.link_content(collection_name, files)

@router.post("/{collection_name}" + UNLINK_CONTENT)
def unlink_content(collection_name: str, file_ids: List[str], response: Response) -> List[UnlinkContentResponse]:
    response.status_code = 207
    return collection_service.unlink_content(collection_name, file_ids)

@router.post("/{collection_name}" + QUERY_COLLECTION)
def query_collection(collection_name: str, request: QueryRequest) -> QueryResponse:
    return collection_service.query_collection(collection_name, request.query, request.enable_critic)

