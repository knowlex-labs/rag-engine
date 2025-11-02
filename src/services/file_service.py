from fastapi import UploadFile
import os
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from models.api_models import FileUploadResponse, ApiResponse, ApiResponseWithBody

class FileService:
    def __init__(self):
        self.upload_dir = "uploads"
        self.metadata_file = os.path.join(self.upload_dir, "files_metadata.json")
        os.makedirs(self.upload_dir, exist_ok=True)

    def _load_metadata(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception:
            pass

    def upload_file(self, file: UploadFile) -> FileUploadResponse:
        try:
            file_id = str(uuid.uuid4())
            file_path = os.path.join(self.upload_dir, f"{file_id}_{file.filename}")

            with open(file_path, "wb") as buffer:
                content = file.file.read()
                buffer.write(content)
            file_size = os.path.getsize(file_path)

            metadata = self._load_metadata()
            metadata[file_id] = {
                "file_id": file_id,
                "filename": file.filename,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "file_path": file_path
            }
            self._save_metadata(metadata)

            return FileUploadResponse(
                status="SUCCESS",
                message="File uploaded successfully",
                body={"file_id": file_id}
            )
        except Exception:
            return FileUploadResponse(
                status="FAILURE",
                message="File upload failed",
                body={}
            )

    def file_exists(self, file_id: str) -> bool:
        files = os.listdir(self.upload_dir)
        for file in files:
            if file.startswith(f"{file_id}_"):
                return True
        return False

    def get_file_path(self, file_id: str) -> Optional[str]:
        files = os.listdir(self.upload_dir)
        for file in files:
            if file.startswith(f"{file_id}_"):
                return os.path.join(self.upload_dir, file)
        return None

    def get_file_content(self, file_id: str) -> Optional[str]:
        file_path = self.get_file_path(file_id)
        if file_path and os.path.exists(file_path):
            file_extension = os.path.splitext(file_path)[1].lower()

            if file_extension == ".pdf":
                return self._extract_pdf_text(file_path)
            else:
                return self._extract_text_file(file_path)
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
        except Exception:
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
        file_path = self.get_file_path(file_id)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                metadata = self._load_metadata()
                if file_id in metadata:
                    del metadata[file_id]
                    self._save_metadata(metadata)

                return True
            except Exception:
                return False
        return False

    def list_files(self) -> List[Dict[str, Any]]:
        metadata = self._load_metadata()
        return list(metadata.values())