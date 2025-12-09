from config import Config
from .storage_interface import StorageServiceInterface
from .minio_storage_service import MinIOStorageService
from .local_storage_service import LocalStorageService
import logging

logger = logging.getLogger(__name__)


def get_storage_service() -> StorageServiceInterface:
    storage_type = Config.storage.STORAGE_TYPE

    if storage_type == "local":
        logger.info("Using LocalStorageService")
        return LocalStorageService()
    elif storage_type == "gcs":
        try:
            from .gcs_storage_service import GCSStorageService
            logger.info("Using GCSStorageService")
            return GCSStorageService()
        except ImportError as e:
            logger.error(f"Failed to import GCS storage service: {e}")
            logger.info("Install google-cloud-storage: pip install google-cloud-storage")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize GCS storage service: {e}")
            raise
    elif storage_type == "s3":
        raise NotImplementedError("S3 storage service not yet implemented")
    elif storage_type == "minio":
        logger.info("Using MinIOStorageService")
        return MinIOStorageService()
    else:
        logger.warning(f"Unknown storage type: {storage_type}, defaulting to MinIO")
        return MinIOStorageService()