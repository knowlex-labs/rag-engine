import os
import tempfile
import logging
from typing import Optional, Iterator, Tuple
from google.cloud import storage
from config import Config
from .storage_interface import StorageServiceInterface

logger = logging.getLogger(__name__)

class GCSStorageService(StorageServiceInterface):
    def __init__(self):
        try:
            self.client = storage.Client()
            self.bucket_name = Config.gcs.BUCKET_NAME
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Initialized GCS Storage with bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize GCS Storage: {e}")
            raise e

    def _get_blob_name(self, storage_path: str) -> str:
        # Remove bucket prefix if accidentally passed (legacy behavior check)
        # Usually storage_path here is object name
        return storage_path

    def download_for_processing(self, storage_path: str) -> Optional[str]:
        try:
            blob = self.bucket.blob(self._get_blob_name(storage_path))
            suffix = os.path.splitext(storage_path)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                blob.download_to_filename(tmp_file.name)
                return tmp_file.name
        except Exception as e:
            logger.error(f"Failed to download from GCS {storage_path}: {e}")
            return None

    def upload_file(self, file_data: bytes, storage_path: str) -> bool:
        try:
            blob = self.bucket.blob(self._get_blob_name(storage_path))
            blob.upload_from_string(file_data)
            return True
        except Exception as e:
            logger.error(f"Failed to upload to GCS {storage_path}: {e}")
            return False

    def delete_file(self, storage_path: str) -> bool:
        try:
            blob = self.bucket.blob(self._get_blob_name(storage_path))
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from GCS {storage_path}: {e}")
            return False

    def exists(self, storage_path: str) -> bool:
        blob = self.bucket.blob(self._get_blob_name(storage_path))
        return blob.exists()

    def get_file_url(self, storage_path: str) -> str:
        # Return public URL pattern as per setup guide
        return f"https://storage.googleapis.com/{self.bucket_name}/{storage_path}"

    def stream_file(self, storage_path: str) -> Iterator[bytes]:
        try:
            blob = self.bucket.blob(self._get_blob_name(storage_path))
            with blob.open("rb") as f:
                while chunk := f.read(8192): # 8KB chunks
                    yield chunk
        except Exception as e:
            logger.error(f"Failed to stream from GCS: {e}")
            yield b""

    def get_content_type_and_size(self, storage_path: str) -> Tuple[str, int]:
        try:
            blob = self.bucket.blob(self._get_blob_name(storage_path))
            blob.reload() # Fetch metadata
            return blob.content_type or "application/octet-stream", blob.size or 0
        except Exception as e:
            logger.error(f"Failed to get metadata from GCS: {e}")
            return "application/octet-stream", 0
