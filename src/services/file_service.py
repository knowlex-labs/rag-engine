from fastapi import UploadFile
import uuid
import logging
import io
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List, Iterator, Tuple
from models.api_models import FileUploadResponse
from models.file_types import FileExtensions, UnsupportedFileTypeError
from services.storage.storage_factory import get_storage_service
from database.postgres_connection import db_connection
from utils.mime_type_detector import get_content_disposition_filename

logger = logging.getLogger(__name__)


class UnifiedFileService:
    def __init__(self):
        self.bucket_prefix = "user-files"
        self.session_user_id = "system_session"
        self.local_storage_path = os.path.join(os.getcwd(), "uploads")
        self.storage_service = get_storage_service()
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

    def _read_file_data(self, storage_path: str) -> Optional[bytes]:
        try:
            if self._is_local_storage(storage_path):
                local_file_path = self.get_local_path(storage_path)
                with open(local_file_path, "rb") as f:
                    return f.read()
            else:
                local_temp_path = self.storage_service.download_for_processing(storage_path)
                if local_temp_path:
                    with open(local_temp_path, "rb") as f:
                        data = f.read()
                    os.remove(local_temp_path)
                    return data
                return None
        except Exception as e:
            logger.error(f"Failed to read file {storage_path}: {e}")
            return None

    def _delete_file_storage(self, storage_path: str) -> bool:
        try:
            return self.storage_service.delete_file(storage_path)
        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {e}")
            return False

    def get_local_file_for_processing(self, file_id: str, user_id: Optional[str]) -> Optional[str]:
        try:
            logger.info(f"get_local_file_for_processing called with file_id={file_id}, user_id={user_id}")
            storage_path = self.get_file_path(file_id, user_id)
            if not storage_path:
                logger.error(f"CRITICAL: get_file_path returned None for file_id={file_id}, user_id={user_id}")
                return None

            logger.info(f"Storage path found: {storage_path}")
            if self._is_local_storage(storage_path):
                local_path = self.get_local_path(storage_path)
                logger.info(f"Local storage, resolved path: {local_path}")
                return local_path
            else:
                logger.info(f"Remote storage, downloading for processing...")
                downloaded_path = self.storage_service.download_for_processing(storage_path)
                logger.info(f"Downloaded to temp path: {downloaded_path}")
                return downloaded_path
        except Exception as e:
            logger.error(f"Failed to get local file for processing: {e}", exc_info=True)
            return None

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

            # Generate storage path based on storage type
            from config import Config
            if Config.storage.STORAGE_TYPE == "local":
                # For local storage: local://absolute_path
                local_file_path = os.path.join(self.local_storage_path, user_id, f"{file_id}_{file.filename}")
                storage_path = f"local://{local_file_path}"
            else:
                # For MinIO/cloud storage: bucket/object
                bucket_name = f"{self.bucket_prefix}"
                object_name = f"{user_id}/{file_id}_{file.filename}"
                storage_path = f"{bucket_name}/{object_name}"

            success = self.storage_service.upload_file(file_content, storage_path)

            if success:

                query = """
                INSERT INTO user_files (id, user_id, filename, file_type, file_size, minio_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                db_connection.execute_query(query, (file_id, user_id, file.filename, file_type, file_size, storage_path))

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
            logger.info(f"get_file_path: file_id={file_id}, user_id={user_id}, actual_user_id={actual_user_id}")
            query = "SELECT minio_path FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))
            if result:
                logger.info(f"File path found in database: {result[0]}")
                return result[0]
            else:
                logger.error(f"CRITICAL: No file found in database for file_id={file_id}, user_id={actual_user_id}")
                return None
        except Exception as e:
            logger.error(f"Database error in get_file_path: {e}", exc_info=True)
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
                logger.warning(f"File {file_id} not found for user {actual_user_id}")
                return False

            minio_path = result[0]
            
            # Step 1: Unlink from all collections and clean up cache
            self._cleanup_file_associations(file_id, actual_user_id)
            
            # Step 2: Delete from storage
            success = self._delete_file_storage(minio_path)

            if success:
                # Step 3: Delete from DB
                delete_query = "DELETE FROM user_files WHERE id = %s AND user_id = %s"
                db_connection.execute_query(delete_query, (file_id, actual_user_id))
                logger.info(f"File {file_id} completely deleted for user {actual_user_id}")

            return success
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def _cleanup_file_associations(self, file_id: str, user_id: str) -> None:
        """Clean up all file associations before deletion"""
        try:
            from utils.cache_manager import CacheManager
            from repositories.collection_repository import collection_repository
            from repositories.qdrant_repository import QdrantRepository
            
            cache_manager = CacheManager()
            qdrant_repo = QdrantRepository()
            
            # Get all collections for this user
            collections = collection_repository.list_collections(user_id)
            
            for collection in collections:
                collection_name = collection.get('name')
                
                # Check if file is linked to this collection
                linked_files = cache_manager.get_collection_files(user_id, collection_name)
                
                if file_id in linked_files:
                    logger.info(f"Unlinking file {file_id} from collection {collection_name}")
                    
                    # Unlink from Qdrant
                    qdrant_collection_name = f"{user_id}_{collection_name}"
                    qdrant_repo.unlink_content(qdrant_collection_name, [file_id])
                    
                    # Remove from collection mapping
                    cache_manager.remove_file_from_collection(user_id, collection_name, file_id)
            
            # Clear chunk cache
            cache_manager.clear_chunks(file_id)
            logger.info(f"Cleaned up all associations for file {file_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup file associations for {file_id}: {e}")
            # Don't raise - continue with file deletion even if cleanup fails

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

    def get_file_info(self, file_id: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get file information for a specific file"""
        try:
            actual_user_id = user_id if user_id else self.session_user_id
            query = "SELECT id, filename, file_type, file_size, upload_date FROM user_files WHERE id = %s AND user_id = %s"
            results = db_connection.execute_query(query, (file_id, actual_user_id))
            if results and len(results) > 0:
                row = results[0]
                return {
                    "file_id": str(row[0]),
                    "filename": row[1],
                    "file_type": row[2],
                    "file_size": row[3],
                    "upload_date": row[4].isoformat() if row[4] else None
                }
            return None
        except Exception as e:
            logger.error(f"Get file info failed for {file_id}: {e}")
            return None

    def stream_file_content(self, file_id: str, user_id: Optional[str]) -> Optional[Tuple[Iterator[bytes], str, str]]:
        """
        Stream file content for HTTP response.

        Args:
            file_id: File ID to stream
            user_id: User ID for access control

        Returns:
            Tuple of (content_stream, content_type, filename) or None if not found/not accessible
        """
        try:
            actual_user_id = user_id if user_id else self.session_user_id

            # Get file metadata and storage path
            query = "SELECT minio_path, filename FROM user_files WHERE id = %s AND user_id = %s"
            result = db_connection.execute_one(query, (file_id, actual_user_id))

            if not result:
                logger.warning(f"File {file_id} not found for user {actual_user_id}")
                return None

            minio_path, filename = result

            # Check if file exists in storage
            if not self.storage_service.exists(minio_path):
                logger.error(f"File not found in storage: {minio_path}")
                return None

            # Get content type and size
            content_type, file_size = self.storage_service.get_content_type_and_size(minio_path)

            # Get clean filename for Content-Disposition
            clean_filename = get_content_disposition_filename(filename)

            # Stream file content
            content_stream = self.storage_service.stream_file(minio_path)

            logger.info(f"Streaming file {file_id} ({clean_filename}) for user {actual_user_id}")

            return content_stream, content_type, clean_filename

        except Exception as e:
            logger.error(f"Failed to stream file content for {file_id}: {e}")
            return None


file_service = UnifiedFileService()