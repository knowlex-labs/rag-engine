
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from typing import Optional, List

from models.api_models import (
    BatchLinkRequest, IngestionResponse,
    RetrieveRequest, RetrieveResponse,
    QueryAnswerRequest, QueryAnswerResponse,
    DeleteFileRequest, DeleteCollectionRequest,
    IndexingStatusResponse, IndexingStatus,
    BatchStatusRequest, BatchStatusResponse, StatusItemResponse
)
from services.collection_service import CollectionService
from services.query_service import QueryService

router = APIRouter()
collection_service = CollectionService()
query_service = QueryService()

@router.post("/link-content", response_model=IngestionResponse, status_code=207)
async def link_content(
    request: BatchLinkRequest,
    x_user_id: str = Header(...)
):
    results = await collection_service.process_batch(request, x_user_id)
    
    return IngestionResponse(
        message="Batch processing complete",
        batch_id="sync_job",
        results=results
    )

@router.post("/query", response_model=QueryAnswerResponse)
async def query(
    request: QueryAnswerRequest,
    x_user_id: str = Header(...)
):
    try:
        collection_name = f"user_{x_user_id}"

        response = query_service.search(
            collection_name=collection_name,
            query_text=request.query,
            collection_ids=request.filters.collection_ids if request.filters else None,
            file_ids=request.filters.file_ids if request.filters else None,
            limit=request.top_k,
            enable_critic=False
        )

        sources = None
        if request.include_sources:
            sources = []
            for chunk in response.chunks:
                sources.append({
                    "chunk_id": "unknown",
                    "chunk_text": chunk.text,
                    "relevance_score": 0.0,
                    "file_id": chunk.source,
                    "page_number": None,
                    "timestamp": None,
                    "concepts": []
                })

        return QueryAnswerResponse(success=True, answer=response.answer, sources=sources)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return QueryAnswerResponse(success=False, answer="Error processing query", sources=None)

@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    request: RetrieveRequest,
    x_user_id: str = Header(...)
):
    try:
        collection_name = f"user_{x_user_id}"

        response = query_service.search(
            collection_name=collection_name,
            query_text=request.query,
            collection_ids=request.filters.collection_ids if request.filters else None,
            file_ids=request.filters.file_ids if request.filters else None,
            limit=request.top_k,
            enable_critic=False
        )

        results = []
        for chunk in response.chunks:
             results.append({
                 "chunk_id": "unknown",
                 "chunk_text": chunk.text,
                 "relevance_score": 0.0,
                 "file_id": chunk.source,
                 "page_number": None,
                 "timestamp": None,
                 "concepts": []
             })

        return RetrieveResponse(success=True, results=results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return RetrieveResponse(success=False, results=[])

@router.post("/status", response_model=BatchStatusResponse)
async def get_status(
    request: BatchStatusRequest,
    x_user_id: str = Header(...)
):
    results = []

    for file_id in request.file_ids:
        status_data = collection_service.get_status(x_user_id, file_id)

        status_value = status_data.get("status", "INDEXING_FAILED")

        results.append(StatusItemResponse(
            file_id=file_id,
            name=status_data.get("name"),
            source=status_data.get("source"),
            status=status_value,
            error=status_data.get("error")
        ))

    return BatchStatusResponse(
        message="Status check complete",
        results=results
    )

@router.delete("/delete/file")
async def delete_file(
    request: DeleteFileRequest,
    x_user_id: str = Header(...)
):
    success = collection_service.unlink_content(
        collection_name=None,
        file_ids=request.file_ids,
        user_id=x_user_id
    )
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete one or more files")
    return {"message": f"Deleted {len(request.file_ids)} file(s)"}

@router.delete("/delete/collection")
async def delete_collection(
    request: DeleteCollectionRequest,
    x_user_id: str = Header(...)
):
    success = collection_service.delete_collection(x_user_id, request.collection_id)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete collection")
    return {"message": "Deleted"}
