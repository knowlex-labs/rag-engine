import os
import logging
from typing import Optional
from .storage_interface import StorageServiceInterface

logger = logging.getLogger(__name__)


class LocalStorageService(StorageServiceInterface):

    def download_for_processing(self, storage_path: str) -> Optional[str]:
        try:
            local_path = storage_path[8:]  # Remove "local://" prefix
            if os.path.exists(local_path):
                return local_path
            else:
                logger.error(f"Local file not found: {local_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to get local file for processing: {e}")
            return None

    def upload_file(self, file_data: bytes, storage_path: str) -> bool:
        try:
            local_path = storage_path[8:]  # Remove "local://" prefix
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)
            return True
        except Exception as e:
            logger.error(f"Failed to upload file locally: {e}")
            return False

    def delete_file(self, storage_path: str) -> bool:
        try:
            local_path = storage_path[8:]  # Remove "local://" prefix
            os.remove(local_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete local file: {e}")
            return False

    def exists(self, storage_path: str) -> bool:
        try:
            local_path = storage_path[8:]  # Remove "local://" prefix
            return os.path.exists(local_path)
        except Exception:
            return False

    def get_file_url(self, storage_path: str) -> str:
        return storage_path