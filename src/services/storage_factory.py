import os

def get_file_service():
    use_unified = os.getenv("USE_UNIFIED_STORAGE", "true").lower() == "true"

    if use_unified:
        from services.file_service import UnifiedFileService
        return UnifiedFileService()
    else:
        gcs_bucket = os.getenv("GCS_BUCKET_NAME", "")
        if gcs_bucket:
            from services.gcs_file_service import GCSFileService
            return GCSFileService()
        else:
            from services.file_service import FileService
            return FileService()
