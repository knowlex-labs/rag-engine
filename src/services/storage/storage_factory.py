from config import Config
from .storage_interface import StorageServiceInterface
from .minio_storage_service import MinIOStorageService
from .local_storage_service import LocalStorageService


def get_storage_service() -> StorageServiceInterface:
    storage_type = Config.storage.STORAGE_TYPE

    if storage_type == "local":
        return LocalStorageService()
    elif storage_type == "s3":
        raise NotImplementedError("S3 storage service not yet implemented")
    elif storage_type == "gcs":
        raise NotImplementedError("GCS storage service not yet implemented")
    else:
        return MinIOStorageService()