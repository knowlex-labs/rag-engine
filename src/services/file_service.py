import shutil
import mimetypes
import logging
import os
import io
import uuid
import glob
import pdfplumber
from typing import List, Optional, Tuple, BinaryIO, Generator
from fastapi import UploadFile

from models.api_models import FileUploadResponse
from models.file_types import FileExtensions, UnsupportedFileTypeError
from services.storage.storage_factory import get_storage_service
from utils.mime_type_detector import get_content_disposition_filename
from config import Config

logger = logging.getLogger(__name__)

class UnifiedFileService:
    def __init__(self):
        self.bucket_prefix = "user-files"
        self.local_storage_path = os.path.join(os.getcwd(), "uploads")
        self.storage_service = get_storage_service()
        self.ensure_local_storage()

    def ensure_local_storage(self):
        try:
            os.makedirs(self.local_storage_path, exist_ok=True)
            logger.info(f"Local storage directory ensured: {self.local_storage_path}")
        except Exception as e:
            logger.error(f"Failed to create local storage directory: {e}")

    def _is_local_storage(self, path: str) -> bool:
        return path and path.startswith("local://")

    def get_local_path(self, minio_path: str) -> str:
        return minio_path[8:]

    def _find_storage_path(self, user_id: str, file_id: str) -> Optional[str]:
        """
        Find storage path for a file_id without DB lookup.
        Searches for files starting with {file_id}_ in the user's directory.
        """
        try:
            # 1. Try Local Storage Strategy
            if Config.storage.STORAGE_TYPE == "local":
                user_dir = os.path.join(self.local_storage_path, user_id)
                if not os.path.exists(user_dir):
                    return None
                
                # Look for {file_id}_*
                pattern = os.path.join(user_dir, f"{file_id}_*")
                matches = glob.glob(pattern)
                
                if matches:
                    # Return the first match formatted as local:// URI
                    return f"local://{matches[0]}"
            
            # 2. Remote Storage Strategy (MinIO/S3)
            # Without DB, we can't easily guess the filename if it varies.
            # But if we assume the standard format is preserved, we might need 'list_objects' capability
            # which might be expensive. 
            # Ideally, the CALLER should provide the filename or full path.
            # For this refactor, we assume Local or that caller provides filename if we add that support.
            # If strictly remote without listing, this will fail.
            # Partial Mitigation: Check if storage service supports listing prefix.
            
            # Fallback: Check if storage has list capability
            # For now, return None if not local.
            logger.warning(f"Storage lookup for {file_id} not fully supported for remote storage without DB")
            return None

        except Exception as e:
            logger.error(f"Error finding storage path for {file_id}: {e}")
            return None

    def get_local_file_for_processing(self, file_id: str, user_id: Optional[str]) -> Optional[str]:
        try:
            if not user_id: 
                logger.error("user_id required for processing")
                return None

            logger.info(f"get_local_file_for_processing: file_id={file_id}, user_id={user_id}")
            
            # Find path using ID
            storage_path = self._find_storage_path(user_id, file_id)
            
            if not storage_path:
                logger.error(f"File path not found for file_id={file_id}")
                return None

            logger.info(f"Storage path found: {storage_path}")
            
            if self._is_local_storage(storage_path):
                local_path = self.get_local_path(storage_path)
                return local_path
            else:
                # Remote download
                return self.storage_service.download_for_processing(storage_path)

        except Exception as e:
            logger.error(f"Failed to get local file for processing: {e}", exc_info=True)
            return None

    def get_file_content(self, file_id: str, user_id: Optional[str]) -> Optional[str]:
        try:
            if not user_id: return None
            
            storage_path = self._find_storage_path(user_id, file_id)
            if not storage_path: return None

            # Read raw bytes
            file_data = None
            if self._is_local_storage(storage_path):
                with open(self.get_local_path(storage_path), "rb") as f:
                    file_data = f.read()
            else:
                local_temp = self.storage_service.download_for_processing(storage_path)
                if local_temp:
                    with open(local_temp, "rb") as f:
                        file_data = f.read()
                    os.remove(local_temp)

            if not file_data: return None

            # Detect type from extension in path
            # storage_path usually ends with extension
            # e.g. local://.../uuid_filename.pdf
            lower_path = storage_path.lower()
            if lower_path.endswith('.pdf'):
                return self.extract_pdf_text(file_data)
            else:
                return self.extract_text_content(file_data)

        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None

    def extract_pdf_text(self, file_data: bytes) -> Optional[str]:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return None

    def extract_text_content(self, file_data: bytes) -> Optional[str]:
        try:
            return file_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return file_data.decode('latin-1')
            except Exception:
                return None

    def detect_file_type(self, filename: str) -> str:
        file_extension = os.path.splitext(filename)[1].lower()
        try:
            file_type = FileExtensions.get_file_type(file_extension)
            return file_type.value
        except UnsupportedFileTypeError as e:
            logger.warning(f"Unsupported file type: {e}")
            raise e

    def upload_file(self, file: UploadFile, user_id: Optional[str]) -> FileUploadResponse:
        # Note: This might not be used by RAG Engine anymore if Teacher handles upload.
        # But keeping it functional for local uploads just in case.
        try:
            if not user_id:
                # Fallback to simple local save if no user
                return self._upload_to_local_storage(file, "system")

            file_id = str(uuid.uuid4())
            file_content = file.file.read()
            
            # Generate storage path: uploads/{user_id}/{file_id}_{filename}
            if Config.storage.STORAGE_TYPE == "local":
                user_dir = os.path.join(self.local_storage_path, user_id)
                os.makedirs(user_dir, exist_ok=True)
                
                local_file_path = os.path.join(user_dir, f"{file_id}_{file.filename}")
                storage_path = f"local://{local_file_path}"
                
                with open(local_file_path, "wb") as f:
                    f.write(file_content)
                
                success = True
            else:
                # Remote
                object_name = f"{user_id}/{file_id}_{file.filename}"
                storage_path = f"{self.bucket_prefix}/{object_name}"
                success = self.storage_service.upload_file(file_content, storage_path)

            if success:
                # No DB insert
                return FileUploadResponse(
                    status="SUCCESS",
                    message="File uploaded successfully",
                    body={"file_id": file_id}
                )
            else:
                return FileUploadResponse(status="FAILURE", message="Upload failed", body={})

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return FileUploadResponse(status="FAILURE", message=str(e), body={})

    def _upload_to_local_storage(self, file: UploadFile, user_subdir: str) -> FileUploadResponse:
        try:
            file_id = str(uuid.uuid4())
            local_filename = f"{file_id}_{file.filename}"
            user_dir = os.path.join(self.local_storage_path, user_subdir)
            os.makedirs(user_dir, exist_ok=True)
            
            local_file_path = os.path.join(user_dir, local_filename)
            with open(local_file_path, "wb") as f:
                f.write(file.file.read())

            return FileUploadResponse(
                status="SUCCESS",
                message="File uploaded locally",
                body={"file_id": file_id}
            )
        except Exception as e:
            return FileUploadResponse(status="FAILURE", message=str(e), body={})

    # Legacy cleanup helper
    def delete_file(self, file_id: str, user_id: str) -> bool:
        # Without DB, we use _find_storage_path and delete file
        path = self._find_storage_path(user_id, file_id)
        if path and self._is_local_storage(path):
            try:
                os.remove(self.get_local_path(path))
                return True
            except (FileNotFoundError, IOError, OSError) as e:
                logger.error(f"Failed to delete file at path {path}: {e}")
                return False
        # Remote delete not implemented blindly without full path
        return False

# Global instance
file_service = UnifiedFileService()