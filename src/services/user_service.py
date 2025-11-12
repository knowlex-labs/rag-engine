import uuid
import logging
from typing import Optional, Dict, Any, List
from repositories.user_repository import user_repository
from services.minio_service import minio_service

logger = logging.getLogger(__name__)


class UserService:

    def generate_anonymous_user_id(self) -> str:
        return f"anonymous_{str(uuid.uuid4())[:8]}"

    def create_anonymous_user(self) -> str:
        try:
            user_id = self.generate_anonymous_user_id()
            user_repository.create_user(user_id, is_anonymous=True)
            logger.info(f"Created anonymous user: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"Failed to create anonymous user: {e}")
            raise e

    def register_user(self, user_id: str, email: str, name: str, anonymous_session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if self.user_exists(user_id):
                return {"status": "SUCCESS", "message": "User already exists", "user_id": user_id}

            user_repository.create_user(user_id, email, name, False)

            if anonymous_session_id and self.user_exists(anonymous_session_id):
                self.migrate_anonymous_data(anonymous_session_id, user_id)

            logger.info(f"Registered user: {user_id}")
            return {"status": "SUCCESS", "message": "User registered successfully", "user_id": user_id}

        except Exception as e:
            logger.error(f"Failed to register user: {e}")
            return {"status": "FAILURE", "message": str(e)}

    def user_exists(self, user_id: str) -> bool:
        try:
            return user_repository.exists(user_id)
        except Exception:
            return False

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            return user_repository.find_by_id(user_id)
        except Exception:
            return None

    def migrate_anonymous_data(self, from_user_id: str, to_user_id: str):
        try:
            logger.info(f"Migrating data from {from_user_id} to {to_user_id}")
            self.migrate_user_files(from_user_id, to_user_id)
            user_repository.delete_by_id(from_user_id)
            logger.info(f"Migration completed from {from_user_id} to {to_user_id}")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise e

    def migrate_user_files(self, from_user_id: str, to_user_id: str):
        try:
            import io
            files = user_repository.get_user_files(from_user_id)
            for file_record in files:
                file_id, old_minio_path = file_record
                bucket_name, old_object_name = old_minio_path.split('/', 1)
                filename = old_object_name.split('/')[-1]
                new_object_name = f"{to_user_id}/{filename}"
                new_minio_path = f"{bucket_name}/{new_object_name}"

                file_data = minio_service.download_file(bucket_name, old_object_name)
                if file_data:
                    file_stream = io.BytesIO(file_data)
                    minio_service.upload_file(bucket_name, new_object_name, file_stream, len(file_data))
                    minio_service.delete_file(bucket_name, old_object_name)
                    user_repository.update_user_file_path(file_id, to_user_id, new_minio_path)

            logger.info(f"Migrated {len(files)} files from {from_user_id} to {to_user_id}")
        except Exception as e:
            logger.error(f"File migration failed: {e}")
            raise e

    def list_users(self) -> List[str]:
        try:
            return user_repository.find_all()
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

    def cleanup_anonymous_users(self, days_old: int = 30):
        try:
            result = user_repository.cleanup_anonymous_users(days_old)
            logger.info(f"Cleaned up {result} anonymous users older than {days_old} days")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


user_service = UserService()