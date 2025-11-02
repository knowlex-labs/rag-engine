from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
from api.api_constants import *
from models.api_models import ApiResponse, ApiResponseWithBody, FileUploadResponse
from services.file_service import FileService

router = APIRouter()
file_service = FileService()

@router.post(FILES_BASE)
def upload_file(file: UploadFile = File(...)) -> FileUploadResponse:
    return file_service.upload_file(file)

@router.get(FILES_BASE)
def list_files() -> ApiResponseWithBody:
    files = file_service.list_files()
    return ApiResponseWithBody(
        status="SUCCESS",
        message="Files retrieved successfully",
        body={"files": files}
    )

@router.get(FILES_BASE + "/{file_id}")
def get_file(file_id: str) -> ApiResponse:
    if file_service.file_exists(file_id):
        return ApiResponse(status="SUCCESS", message=f"File '{file_id}' retrieved successfully")
    else:
        return ApiResponse(status="FAILURE", message="File not found")


@router.delete(FILES_BASE + "/{file_id}")
def delete_file(file_id: str) -> ApiResponse:
    success = file_service.delete_file(file_id)
    if success:
        return ApiResponse(status="SUCCESS", message=f"File '{file_id}' deleted successfully")
    else:
        return ApiResponse(status="FAILURE", message="File not found or could not be deleted")