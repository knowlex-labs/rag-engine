import logging
from services.file_service import file_service
from database.postgres_connection import db_connection
from config import Config

logger = logging.getLogger(__name__)

class FileOrganizerService:

    def move_to_collection(self, file_id: str, user_id: str, collection_name: str) -> bool:
        collection_id = self._get_collection_id(user_id, collection_name)
        if not collection_id:
            logger.error(f"Collection '{collection_name}' not found for user '{user_id}'")
            return False

        self._update_db_parent_folder(file_id, user_id, collection_id)

        logger.info(f"Storage type: {Config.storage.STORAGE_TYPE}")
        if Config.storage.STORAGE_TYPE != "gcs":
            logger.info(f"Storage type {Config.storage.STORAGE_TYPE} - skipping file move")
            return True

        file_info = file_service.get_file_info(file_id, user_id)
        if not file_info:
            return False

        current_path = file_service.get_file_path(file_id, user_id)
        if not current_path:
            return False

        clean_name = collection_name.replace(' ', '_').replace('/', '_')
        new_path = f"collections/{clean_name}/{file_id}_{file_info['filename']}"

        return self._move_file(file_id, user_id, current_path, new_path, collection_id)

    def move_to_user_folder(self, file_id: str, user_id: str) -> bool:
        self._update_db_parent_folder(file_id, user_id, None)

        if Config.storage.STORAGE_TYPE != "gcs":
            logger.debug(f"Storage type {Config.storage.STORAGE_TYPE} - skipping file move")
            return True

        file_info = file_service.get_file_info(file_id, user_id)
        if not file_info:
            return False

        current_path = file_service.get_file_path(file_id, user_id)
        if not current_path:
            return False

        new_path = f"{user_id}/{file_id}_{file_info['filename']}"

        return self._move_file(file_id, user_id, current_path, new_path, None)

    def _move_file(self, file_id: str, user_id: str, current_path: str, new_path: str, parent_folder_id: str = None) -> bool:
        try:
            storage = file_service.storage_service

            if storage.exists(new_path):
                logger.debug(f"File already at destination: {new_path}")
                return True

            file_data = file_service._read_file_data(current_path)
            if not file_data:
                return False

            if not storage.upload_file(file_data, new_path):
                return False

            storage.delete_file(current_path)
            self._update_db_path(file_id, user_id, new_path)
            self._update_db_parent_folder(file_id, user_id, parent_folder_id)

            logger.info(f"Moved file {file_id}: {current_path} → {new_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to move file {file_id}: {e}")
            return False

    def _update_db_path(self, file_id: str, user_id: str, new_path: str):
        query = "UPDATE user_files SET minio_path = %s WHERE id = %s AND user_id = %s"
        db_connection.execute_query(query, (new_path, file_id, user_id))

    def _update_db_parent_folder(self, file_id: str, user_id: str, parent_folder_id: str):
        query = "UPDATE user_files SET parent_folder_id = %s WHERE id = %s AND user_id = %s"
        db_connection.execute_query(query, (parent_folder_id, file_id, user_id))

    def _get_collection_id(self, user_id: str, collection_name: str) -> str:
        query = "SELECT id FROM user_collections WHERE user_id = %s AND collection_name = %s"
        result = db_connection.execute_one(query, (user_id, collection_name))
        return str(result[0]) if result else None

file_organizer = FileOrganizerService()