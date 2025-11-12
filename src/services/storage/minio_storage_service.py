import tempfile
import os
import logging
from typing import Optional
from .storage_interface import StorageServiceInterface
from services.minio_service import minio_service

logger = logging.getLogger(__name__)


class MinIOStorageService(StorageServiceInterface):

    def download_for_processing(self, storage_path: str) -> Optional[str]:
        try:
            bucket_name, object_name = storage_path.split('/', 1)
            file_data = minio_service.download_file(bucket_name, object_name)
            if not file_data:
                return None

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(file_data)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Failed to download file for processing: {e}")
            return None

    def upload_file(self, file_data: bytes, storage_path: str) -> bool:
        try:
            bucket_name, object_name = storage_path.split('/', 1)
            import io
            file_stream = io.BytesIO(file_data)
            return minio_service.upload_file(bucket_name, object_name, file_stream, len(file_data))
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    def delete_file(self, storage_path: str) -> bool:
        try:
            bucket_name, object_name = storage_path.split('/', 1)
            return minio_service.delete_file(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            bucket_name, object_name = storage_path.split('/', 1)
            file_data = minio_service.download_file(bucket_name, object_name)
            return file_data is not None
        except Exception:
            return False

    def get_file_url(self, storage_path: str) -> str:
        bucket_name, object_name = storage_path.split('/', 1)
        return minio_service.get_file_url(bucket_name, object_name)