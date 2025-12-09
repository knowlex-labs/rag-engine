"""
Google Cloud Storage implementation of the storage interface.
"""

import os
import logging
from typing import Optional, Iterator, Tuple
from .storage_interface import StorageServiceInterface
from utils.mime_type_detector import get_mime_type

logger = logging.getLogger(__name__)

class GCSStorageService(StorageServiceInterface):
    def __init__(self):
        try:
            from google.cloud import storage
            self.client = storage.Client()

            # Get bucket configuration
            from config import Config
            self.bucket_name = Config.gcs.BUCKET_NAME
            self.bucket = self.client.bucket(self.bucket_name)

            logger.info(f"GCS client initialized for bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise

    def upload_file(self, file_data: bytes, storage_path: str) -> bool:
        """Upload file to Google Cloud Storage."""
        try:
            # Create blob object
            blob = self.bucket.blob(storage_path)

            # Set content type based on file extension
            mime_type = get_mime_type(storage_path)
            blob.content_type = mime_type

            # Upload file data
            blob.upload_from_string(
                file_data,
                content_type=mime_type
            )

            # Try to make blob publicly readable (skip if uniform bucket access is enabled)
            try:
                blob.make_public()
                logger.info(f"Made {storage_path} publicly accessible")
            except Exception as acl_error:
                # This is expected with uniform bucket-level access
                logger.info(f"Skipping ACL for {storage_path} - likely uniform bucket access: {acl_error}")

            logger.info(f"Successfully uploaded {storage_path} to GCS")
            return True

        except Exception as e:
            logger.error(f"Failed to upload {storage_path} to GCS: {e}")
            return False

    def download_for_processing(self, storage_path: str) -> Optional[str]:
        """Download file to temporary location for processing."""
        try:
            import tempfile

            blob = self.bucket.blob(storage_path)

            if not blob.exists():
                logger.error(f"GCS blob not found: {storage_path}")
                return None

            # Create temporary file
            suffix = os.path.splitext(storage_path)[1] or '.tmp'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

            # Download to temporary file
            blob.download_to_filename(temp_file.name)
            temp_file.close()

            logger.info(f"Downloaded {storage_path} to temp file: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Failed to download {storage_path} for processing: {e}")
            return None

    def delete_file(self, storage_path: str) -> bool:
        """Delete file from Google Cloud Storage."""
        try:
            blob = self.bucket.blob(storage_path)

            if not blob.exists():
                logger.warning(f"GCS blob not found for deletion: {storage_path}")
                return False

            blob.delete()
            logger.info(f"Successfully deleted {storage_path} from GCS")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {storage_path} from GCS: {e}")
            return False

    def exists(self, storage_path: str) -> bool:
        """Check if file exists in Google Cloud Storage."""
        try:
            blob = self.bucket.blob(storage_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Failed to check existence of {storage_path}: {e}")
            return False

    def get_file_url(self, storage_path: str) -> str:
        """Get public URL for file in Google Cloud Storage."""
        # Return public GCS URL for direct access
        return f"https://storage.googleapis.com/{self.bucket_name}/{storage_path}"

    def stream_file(self, storage_path: str) -> Iterator[bytes]:
        """Stream file content in chunks for efficient handling of large files."""
        try:
            blob = self.bucket.blob(storage_path)

            if not blob.exists():
                logger.error(f"GCS blob not found for streaming: {storage_path}")
                return iter([])

            # Stream file in chunks
            chunk_size = 8192  # 8KB chunks
            with blob.open("rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk

        except Exception as e:
            logger.error(f"Failed to stream {storage_path} from GCS: {e}")
            return iter([])

    def get_content_type_and_size(self, storage_path: str) -> Tuple[str, int]:
        """Get MIME content type and file size for HTTP headers."""
        try:
            blob = self.bucket.blob(storage_path)

            if not blob.exists():
                logger.error(f"GCS blob not found for metadata: {storage_path}")
                return "application/octet-stream", 0

            # Reload to get latest metadata
            blob.reload()

            # Get content type (use detected if not set)
            content_type = blob.content_type or get_mime_type(storage_path)

            # Get file size
            file_size = blob.size or 0

            return content_type, file_size

        except Exception as e:
            logger.error(f"Failed to get metadata for {storage_path}: {e}")
            return "application/octet-stream", 0

    def get_public_url(self, storage_path: str) -> str:
        """Get public URL that can be accessed directly without authentication."""
        return self.get_file_url(storage_path)