from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, UploadFile, File
from typing import Optional, List
import shutil
import uuid
import os
import logging

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

from api.api_constants import LINK_CONTENT, QUERY_COLLECTION, COLLECTION_STATUS, UNLINK_CONTENT

router = APIRouter()
logger = logging.getLogger(__name__)
collection_service = CollectionService()
query_service = QueryService()

@router.post(LINK_CONTENT, response_model=IngestionResponse, status_code=207)
async def link_content(
    request: BatchLinkRequest,
    x_user_id: str = Header(...)
):
    logger.info(f"Linking content for user {x_user_id}: {len(request.items)} items")
    results = await collection_service.process_batch(request, x_user_id)
    
    return IngestionResponse(
        message="Batch processing complete",
        batch_id="sync_job",
        results=results
    )

@router.post(QUERY_COLLECTION, response_model=QueryAnswerResponse)
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
                    "chunk_id": chunk.chunk_id or "unknown",
                    "chunk_text": chunk.text,
                    "relevance_score": chunk.relevance_score or 0.0,
                    "file_id": chunk.file_id or chunk.source,
                    "page_number": chunk.page_number,
                    "timestamp": chunk.timestamp,
                    "concepts": chunk.concepts
                })

        return QueryAnswerResponse(success=True, answer=response.answer, sources=sources)
    except Exception as e:
        import logging
        logging.error("Error processing query", exc_info=True)
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
                 "chunk_id": chunk.chunk_id or "unknown",
                 "chunk_text": chunk.text,
                 "relevance_score": chunk.relevance_score or 0.0,
                 "file_id": chunk.file_id or chunk.source,
                 "page_number": chunk.page_number,
                 "timestamp": chunk.timestamp,
                 "concepts": chunk.concepts
             })

        return RetrieveResponse(success=True, results=results)
    except Exception as e:
        import logging
        logging.error("Error retrieving results", exc_info=True)
        return RetrieveResponse(success=False, results=[])

@router.post(COLLECTION_STATUS, response_model=BatchStatusResponse)
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

@router.delete(UNLINK_CONTENT)
async def delete_file(
    request: DeleteFileRequest,
    x_user_id: str = Header(...)
):
    count = collection_service.unlink_content(
        collection_name=None,
        file_ids=request.file_ids,
        user_id=x_user_id
    )
    return {"message": f"Deleted {count} file(s)"}


@router.delete("/delete/collection")
async def delete_collection(
    request: DeleteCollectionRequest,
    x_user_id: str = Header(...)
):
    success = collection_service.delete_collection(x_user_id, request.collection_id)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete collection")
    return {"message": "Deleted"}

# Legal GraphRAG Endpoints
from services.legal_ingestion_service import legal_ingestion_service
from services.question_generator_service import question_generator


@router.post("/ingest/legal-graph")
async def ingest_legal_document_graph(file: UploadFile = File(...)):
    """
    Triggers Legal GraphRAG ingestion for an uploaded file.
    """
    try:
        file_id = str(uuid.uuid4())
        # Sanitizing filename to avoid path traversal issues, simpler way for now
        safe_filename = os.path.basename(file.filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{safe_filename}", mode="wb") as buffer:
            temp_file_path = buffer.name
            shutil.copyfileobj(file.file, buffer)
            
        try:
            await legal_ingestion_service.ingest_document(temp_file_path, file_id)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
        return {"status": "success", "message": f"Ingested {file.filename} into Legal Graph.", "file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/match-list")
async def generate_match_list_question(file_id: str = None):
    """
    Generates a Match List question from the Knowledge Graph.
    """
    result = question_generator.generate_match_list(file_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.post("/generate/assertion-reason")
async def generate_assertion_reason_question(file_id: str = None):
    """
    Generates an Assertion-Reason question from the Knowledge Graph.
    """
    result = question_generator.generate_assertion_reason(file_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
