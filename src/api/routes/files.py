from fastapi import APIRouter, HTTPException, UploadFile, File, Header
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

@router.delete(FILES_BASE + "/{file_id}")
def delete_file(file_id: str, x_user_id: str = Header(...)) -> ApiResponse:
    validate_user(x_user_id)
    if not file_service.delete_file(file_id, x_user_id):
        raise HTTPException(status_code=404, detail="File not found")
    return ApiResponse(status="SUCCESS", message=f"File '{file_id}' deleted successfully")