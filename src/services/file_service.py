from fastapi import UploadFile
import uuid
import logging
import io
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List
from models.api_models import FileUploadResponse
from models.file_types import FileExtensions, UnsupportedFileTypeError
from services.minio_service import minio_service
from database.postgres_connection import db_connection

logger = logging.getLogger(__name__)


class UnifiedFileService:
    def __init__(self):
        self.bucket_prefix = "user-files"
        self.session_user_id = "system_session"
        self.local_storage_path = os.path.join(os.getcwd(), "uploads")
        self.ensure_local_storage()
        self.init_database()
        self.ensure_session_user()

    def ensure_local_storage(self):
        try:
            os.makedirs(self.local_storage_path, exist_ok=True)
            logger.info(f"Local storage directory ensured: {self.local_storage_path}")
        except Exception as e:
            logger.error(f"Failed to create local storage directory: {e}")

    def ensure_session_user(self):
        try:
            from services.user_service import user_service
            if not user_service.user_exists(self.session_user_id):
                query = "INSERT INTO users (id, name, is_anonymous) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING"
                db_connection.execute_query(query, (self.session_user_id, "System Session", True))
                logger.info(f"Session user created: {self.session_user_id}")
        except Exception as e:
            logger.error(f"Failed to create session user: {e}")

    def _is_local_storage(self, path: str) -> bool:
        return path.startswith("local://")

    def get_local_path(self, minio_path: str) -> str:
        return minio_path[8:]

    def _read_file_data(self, minio_path: str) -> Optional[bytes]:
        try:
            if self._is_local_storage(minio_path):
                local_file_path = self.get_local_path(minio_path)
                with open(local_file_path, "rb") as f:
                    return f.read()
            else:
                bucket_name, object_name = minio_path.split('/', 1)
                return minio_service.download_file(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Failed to read file {minio_path}: {e}")
            return None

    def _delete_file_storage(self, minio_path: str) -> bool:
        try:
            if self._is_local_storage(minio_path):
                local_file_path = self.get_local_path(minio_path)
                os.remove(local_file_path)
                return True
            else:
                bucket_name, object_name = minio_path.split('/', 1)
                return minio_service.delete_file(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Failed to delete file {minio_path}: {e}")
            return False

    def init_database(self):
        try:
            schema_query = """
            CREATE TABLE IF NOT EXISTS user_files (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL REFERENCES users(id),
                filename VARCHAR(500) NOT NULL,
                file_type VARCHAR(50) NOT NULL,
                file_size BIGINT NOT NULL,
                minio_path VARCHAR(1000) NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON user_files(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_files_file_type ON user_files(file_type);
            CREATE INDEX IF NOT EXISTS idx_user_files_upload_date ON user_files(upload_date);
            """
            db_connection.execute_query(schema_query)
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def detect_file_type(self, filename: str) -> str:
        import os
        file_extension = os.path.splitext(filename)[1].lower()
        try:
            file_type = FileExtensions.get_file_type(file_extension)
            return file_type.value
        except UnsupportedFileTypeError as e:
            logger.warning(f"Unsupported file type: {e}")
            raise e

    def upload_file(self, file: UploadFile, user_id: Optional[str]) -> FileUploadResponse:
        try:
            if not user_id:
                return self._upload_to_local_storage(file)

            file_id = str(uuid.uuid4())
            file_content = file.file.read()
            file_size = len(file_content)
            file_type = self.detect_file_type(file.filename)

            bucket_name = f"{self.bucket_prefix}"
            object_name = f"{user_id}/{file_id}_{file.filename}"

            file_data = io.BytesIO(file_content)
            success = minio_service.upload_file(bucket_name, object_name, file_data, file_size)

            if success:
                minio_path = f"{bucket_name}/{object_name}"

                query = """
                INSERT INTO user_files (id, user_id, filename, file_type, file_size, minio_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                db_connection.execute_query(query, (file_id, user_id, file.filename, file_type, file_size, minio_path))

                return FileUploadResponse(
                    status="SUCCESS",
                    message="File uploaded successfully",
                    body={"file_id": file_id}
                )
            else:
                return FileUploadResponse(
                    status="FAILURE",
                    message="Failed to upload file to storage",
                    body={}
                )

        except UnsupportedFileTypeError as e:
            return FileUploadResponse(
                status="FAILURE",
                message=f"Unsupported file type: {str(e)}",
                body={}
            )
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return FileUploadResponse(
                status="FAILURE",
                message=f"Upload failed: {str(e)}",
                body={}
            )

    def file_exists(self, file_id: str, user_id: Optional[str]) -> bool:
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT id FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))
            return result is not None
        except Exception:
            return False

    def get_file_path(self, file_id: str, user_id: Optional[str]) -> Optional[str]:
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT minio_path FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))
            return result[0] if result else None
        except Exception:
            return None

    def get_file_content(self, file_id: str, user_id: Optional[str]) -> Optional[str]:
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT minio_path, file_type FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))

            if not result:
                return None

            minio_path, file_type = result
            file_data = self._read_file_data(minio_path)

            if not file_data:
                return None

            if file_type == "pdf":
                return self.extract_pdf_text(file_data)
            else:
                return self.extract_text_content(file_data)

        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None

    def extract_pdf_text(self, file_data: bytes) -> Optional[str]:
        try:
            import pdfplumber
            import io

            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return None

    def extract_text_content(self, file_data: bytes) -> Optional[str]:
        try:
            return file_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return file_data.decode('latin-1')
            except Exception:
                return None

    def delete_file(self, file_id: str, user_id: Optional[str]) -> bool:
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT minio_path FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))

            if not result:
                return False

            minio_path = result[0]
            success = self._delete_file_storage(minio_path)

            if success:
                delete_query = "DELETE FROM user_files WHERE id = %s AND user_id = %s"
                db_connection.execute_query(delete_query, (file_id, actual_user_id))

            return success
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def _upload_to_local_storage(self, file: UploadFile) -> FileUploadResponse:
        try:
            file_id = str(uuid.uuid4())
            file_content = file.file.read()
            file_size = len(file_content)
            file_type = self.detect_file_type(file.filename)

            local_filename = f"{file_id}_{file.filename}"
            local_file_path = os.path.join(self.local_storage_path, local_filename)

            with open(local_file_path, "wb") as f:
                f.write(file_content)

            local_path = f"local://{local_file_path}"
            query = """
            INSERT INTO user_files (id, user_id, filename, file_type, file_size, minio_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            db_connection.execute_query(query, (file_id, self.session_user_id, file.filename, file_type, file_size, local_path))

            logger.info(f"File uploaded to local storage: {local_file_path}")
            return FileUploadResponse(
                status="SUCCESS",
                message="File uploaded to local storage successfully",
                body={"file_id": file_id}
            )

        except Exception as e:
            logger.error(f"Local upload failed: {e}")
            return FileUploadResponse(
                status="FAILURE",
                message=f"Local upload failed: {str(e)}",
                body={}
            )

    def list_files(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT id, filename, file_type, file_size, upload_date FROM user_files WHERE user_id = %s ORDER BY upload_date DESC"
            results = db_connection.execute_query(query, (actual_user_id,))

            files = []
            for row in results:
                files.append({
                    "file_id": str(row[0]),
                    "filename": row[1],
                    "file_type": row[2],
                    "file_size": row[3],
                    "upload_date": row[4].isoformat() if row[4] else None
                })
            return files
        except Exception as e:
            logger.error(f"List files failed: {e}")
            return []


file_service = UnifiedFileService()