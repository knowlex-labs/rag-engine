from config import Config
from .storage_interface import StorageServiceInterface
from .minio_storage_service import MinIOStorageService
from .local_storage_service import LocalStorageService
from .gcs_storage_service import GCSStorageService


def get_storage_service() -> StorageServiceInterface:
    storage_type = Config.storage.STORAGE_TYPE

    if storage_type == "local":
        return LocalStorageService()
    elif storage_type == "gcs":
        return GCSStorageService()
    elif storage_type == "minio":
        return MinIOStorageService()
    else:
        raise NotImplementedError(f"Storage type '{storage_type}' not implemented")