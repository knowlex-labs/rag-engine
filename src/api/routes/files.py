from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from fastapi.responses import StreamingResponse
import logging
from api.api_constants import *
from models.api_models import ApiResponse, ApiResponseWithBody, FileUploadResponse
from services.file_service import file_service
from services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter()

def validate_user(user_id: str):
    if not user_service.ensure_user_exists(user_id):
        logger.warning(f"Failed to create user {user_id}, proceeding with anonymous fallback")

@router.post(FILES_BASE)
def upload_file(file: UploadFile = File(...), x_user_id: str = Header(...)) -> FileUploadResponse:
    validate_user(x_user_id)
    result = file_service.upload_file(file, x_user_id)
    if result.status == "FAILURE":
        raise HTTPException(status_code=400, detail=result.message)
    return result

@router.get(FILES_BASE)
def list_files(x_user_id: str = Header(...)) -> ApiResponseWithBody:
    validate_user(x_user_id)
    files = file_service.list_files(x_user_id)
    return ApiResponseWithBody(
        status="SUCCESS",
        message="Files retrieved successfully",
        body={"files": files}
    )

@router.get(FILES_BASE + "/{file_id}")
def get_file(file_id: str, x_user_id: str = Header(...)) -> ApiResponse:
    validate_user(x_user_id)
    if not file_service.file_exists(file_id, x_user_id):
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(status="SUCCESS", message=f"File '{file_id}' retrieved successfully")

@router.get(FILES_BASE + "/{file_id}/content")
def get_file_content(file_id: str, x_user_id: str = Header(...)):
    """
    Stream file content with proper MIME type and Content-Disposition headers.
    Returns raw file bytes for direct viewing (PDFs) or downloading.
    """
    validate_user(x_user_id)

    # Get file stream and metadata
    result = file_service.stream_file_content(file_id, x_user_id)

    if not result:
        raise HTTPException(status_code=404, detail="File not found")

    content_stream, content_type, filename = result

    # Create response headers for proper file handling
    headers = {
        "Content-Type": content_type,
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
    }

    logger.info(f"Serving file content: {filename} ({content_type}) for user {x_user_id}")

    return StreamingResponse(
        content=content_stream,
        headers=headers,
        media_type=content_type
    )

@router.delete(FILES_BASE + "/{file_id}")
def delete_file(file_id: str, x_user_id: str = Header(...)) -> ApiResponse:
    validate_user(x_user_id)
    if not file_service.delete_file(file_id, x_user_id):
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(status="SUCCESS", message=f"File '{file_id}' deleted successfully")