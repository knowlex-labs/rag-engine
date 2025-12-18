import tempfile
import os
import logging
from typing import Optional, Iterator, Tuple
from .storage_interface import StorageServiceInterface
from services.minio_service import minio_service
from utils.mime_type_detector import get_mime_type

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

    def stream_file(self, storage_path: str) -> Iterator[bytes]:
        """Stream file content in chunks for efficient handling of large files."""
        try:
            bucket_name, object_name = storage_path.split('/', 1)
            return minio_service.stream_file(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Failed to stream file from MinIO: {e}")
            return iter([])

    def get_content_type_and_size(self, storage_path: str) -> Tuple[str, int]:
        """Get MIME content type and file size for HTTP headers."""
        try:
            bucket_name, object_name = storage_path.split('/', 1)

            # Try to get info from MinIO metadata first
            info = minio_service.get_object_info(bucket_name, object_name)
            if info:
                file_size, minio_content_type = info

                # Use our MIME type detection if MinIO doesn't have it or has generic type
                if minio_content_type in ('application/octet-stream', None):
                    mime_type = get_mime_type(object_name)
                else:
                    mime_type = minio_content_type

                return mime_type, file_size
            else:
                # Fallback if object info fails
                logger.warning(f"Could not get MinIO object info for {storage_path}")
                return get_mime_type(object_name), 0

        except Exception as e:
            logger.error(f"Failed to get content type and size for MinIO file: {e}")
            return "application/octet-stream", 0