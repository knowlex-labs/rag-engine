"""
Storage Factory - Auto-selects between local and GCS storage based on environment
"""
import os

def get_file_service():
    """
    Returns appropriate file service based on environment configuration.
    - If GCS_BUCKET_NAME is set, uses GCSFileService
    - Otherwise, uses local FileService
    """
    gcs_bucket = os.getenv("GCS_BUCKET_NAME", "")

    if gcs_bucket:
        print(f"🌐 Initializing GCS File Service with bucket: {gcs_bucket}")
        from services.gcs_file_service import GCSFileService
        return GCSFileService()
    else:
        print("💾 Initializing Local File Service")
        from services.file_service import FileService
        return FileService()
