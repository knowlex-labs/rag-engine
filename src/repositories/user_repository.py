import logging
from typing import Optional, Dict, Any, List
from database.postgres_connection import db_connection

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self):
        self.init_schema()

    def init_schema(self):
        try:
            users_table = """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(255) PRIMARY KEY,
                email VARCHAR(255),
                name VARCHAR(255),
                is_anonymous BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            user_files_table = """
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
            """

            indexes = """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_is_anonymous ON users(is_anonymous);
            CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON user_files(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_files_file_type ON user_files(file_type);
            CREATE INDEX IF NOT EXISTS idx_user_files_upload_date ON user_files(upload_date);
            """

            db_connection.execute_query(users_table)
            db_connection.execute_query(user_files_table)
            db_connection.execute_query(indexes)

            logger.info("User schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize user schema: {e}")

    def create_user(self, user_id: str, email: str = None, name: str = None, is_anonymous: bool = False):
        query = "INSERT INTO users (id, email, name, is_anonymous) VALUES (%s, %s, %s, %s)"
        db_connection.execute_query(query, (user_id, email, name, is_anonymous))

    def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT id, email, name, is_anonymous, created_at FROM users WHERE id = %s"
        result = db_connection.execute_one(query, (user_id,))
        if result:
            return {
                "id": result[0],
                "email": result[1],
                "name": result[2],
                "is_anonymous": result[3],
                "created_at": result[4].isoformat() if result[4] else None
            }
        return None

    def exists(self, user_id: str) -> bool:
        query = "SELECT id FROM users WHERE id = %s"
        result = db_connection.execute_one(query, (user_id,))
        return result is not None

    def find_all(self) -> List[str]:
        query = "SELECT id FROM users ORDER BY created_at DESC"
        results = db_connection.execute_query(query)
        return [row[0] for row in results] if results else []

    def delete_by_id(self, user_id: str):
        query = "DELETE FROM users WHERE id = %s"
        db_connection.execute_query(query, (user_id,))

    def cleanup_anonymous_users(self, days_old: int = 30):
        query = "DELETE FROM users WHERE is_anonymous = true AND created_at < NOW() - INTERVAL '%s days'"
        return db_connection.execute_query(query, (days_old,))

    def get_user_files(self, user_id: str) -> List[tuple]:
        query = "SELECT id, minio_path FROM user_files WHERE user_id = %s"
        return db_connection.execute_query(query, (user_id,))

    def update_user_file_path(self, file_id: str, user_id: str, minio_path: str):
        query = "UPDATE user_files SET user_id = %s, minio_path = %s WHERE id = %s"
        db_connection.execute_query(query, (user_id, minio_path, file_id))


user_repository = UserRepository()