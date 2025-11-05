from fastapi import UploadFile
import os
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from models.api_models import FileUploadResponse, ApiResponse, ApiResponseWithBody
from google.cloud import storage
import tempfile

class GCSFileService:
    """
    File service using Google Cloud Storage for production deployment.
    Falls back to local storage if GCS is not configured.
    """
    def __init__(self):
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "")
        self.use_gcs = bool(self.bucket_name)

        if self.use_gcs:
            try:
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(self.bucket_name)
                self.metadata_blob_name = "metadata/files_metadata.json"
                print(f"✅ Using Google Cloud Storage: {self.bucket_name}")
            except Exception as e:
                print(f"⚠️ GCS init failed, falling back to local storage: {e}")
                self.use_gcs = False

        if not self.use_gcs:
            # Fallback to local storage
            self.upload_dir = "uploads"
            self.metadata_file = os.path.join(self.upload_dir, "files_metadata.json")
            os.makedirs(self.upload_dir, exist_ok=True)
            print(f"✅ Using local storage: {self.upload_dir}")

    def _load_metadata(self) -> Dict[str, Any]:
        try:
            if self.use_gcs:
                blob = self.bucket.blob(self.metadata_blob_name)
                if blob.exists():
                    metadata_json = blob.download_as_text()
                    return json.loads(metadata_json)
                return {}
            else:
                if os.path.exists(self.metadata_file):
                    with open(self.metadata_file, "r") as f:
                        return json.load(f)
                return {}
        except Exception as e:
            print(f"Error loading metadata: {e}")
            return {}

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        try:
            if self.use_gcs:
                blob = self.bucket.blob(self.metadata_blob_name)
                blob.upload_from_string(
                    json.dumps(metadata, indent=2),
                    content_type="application/json"
                )
            else:
                with open(self.metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving metadata: {e}")

    def upload_file(self, file: UploadFile) -> FileUploadResponse:
        try:
            file_id = str(uuid.uuid4())
            file_content = file.file.read()

            if self.use_gcs:
                # Upload to GCS
                blob_name = f"files/{file_id}_{file.filename}"
                blob = self.bucket.blob(blob_name)
                blob.upload_from_string(file_content)
                file_size = len(file_content)
                storage_path = f"gs://{self.bucket_name}/{blob_name}"
            else:
                # Upload to local storage
                file_path = os.path.join(self.upload_dir, f"{file_id}_{file.filename}")
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                file_size = os.path.getsize(file_path)
                storage_path = file_path

            metadata = self._load_metadata()
            metadata[file_id] = {
                "file_id": file_id,
                "filename": file.filename,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "file_path": storage_path
            }
            self._save_metadata(metadata)

            return FileUploadResponse(
                status="SUCCESS",
                message="File uploaded successfully",
                body={"file_id": file_id}
            )
        except Exception as e:
            print(f"File upload error: {e}")
            return FileUploadResponse(
                status="FAILURE",
                message=f"File upload failed: {str(e)}",
                body={}
            )

    def file_exists(self, file_id: str) -> bool:
        try:
            if self.use_gcs:
                blobs = self.bucket.list_blobs(prefix=f"files/{file_id}_")
                return any(True for _ in blobs)
            else:
                files = os.listdir(self.upload_dir)
                return any(file.startswith(f"{file_id}_") for file in files)
        except Exception:
            return False

    def get_file_path(self, file_id: str) -> Optional[str]:
        try:
            metadata = self._load_metadata()
            if file_id in metadata:
                return metadata[file_id]["file_path"]
            return None
        except Exception:
            return None

    def get_file_content(self, file_id: str) -> Optional[str]:
        try:
            file_path = self.get_file_path(file_id)
            if not file_path:
                return None

            if self.use_gcs and file_path.startswith("gs://"):
                # Download from GCS to temp file
                blob_name = file_path.replace(f"gs://{self.bucket_name}/", "")
                blob = self.bucket.blob(blob_name)

                # Determine file extension
                file_extension = os.path.splitext(blob_name)[1].lower()

                if file_extension == ".pdf":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        blob.download_to_filename(tmp_file.name)
                        content = self._extract_pdf_text(tmp_file.name)
                        os.unlink(tmp_file.name)
                        return content
                else:
                    # Text file - download directly as string
                    return blob.download_as_text()
            else:
                # Local file
                if os.path.exists(file_path):
                    file_extension = os.path.splitext(file_path)[1].lower()
                    if file_extension == ".pdf":
                        return self._extract_pdf_text(file_path)
                    else:
                        return self._extract_text_file(file_path)
            return None
        except Exception as e:
            print(f"Error getting file content: {e}")
            return None

    def _extract_pdf_text(self, file_path: str) -> Optional[str]:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text.strip() else None
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return None

    def _extract_text_file(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except Exception:
                return None
        except Exception:
            return None

    def delete_file(self, file_id: str) -> bool:
        try:
            file_path = self.get_file_path(file_id)
            if not file_path:
                return False

            if self.use_gcs and file_path.startswith("gs://"):
                # Delete from GCS
                blob_name = file_path.replace(f"gs://{self.bucket_name}/", "")
                blob = self.bucket.blob(blob_name)
                blob.delete()
            else:
                # Delete local file
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Remove from metadata
            metadata = self._load_metadata()
            if file_id in metadata:
                del metadata[file_id]
                self._save_metadata(metadata)

            return True
        except Exception as e:
            print(f"Delete file error: {e}")
            return False

    def list_files(self) -> List[Dict[str, Any]]:
        try:
            metadata = self._load_metadata()
            return list(metadata.values())
        except Exception:
            return []
