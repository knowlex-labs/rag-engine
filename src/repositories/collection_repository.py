import logging
from typing import Optional, Dict, Any, List
from database.postgres_connection import db_connection
import json

logger = logging.getLogger(__name__)


class CollectionRepository:
    def __init__(self):
        self.init_schema()

    def init_schema(self):
        try:
            user_collections_table = """
            CREATE TABLE IF NOT EXISTS user_collections (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL REFERENCES users(id),
                collection_name VARCHAR(255) NOT NULL,
                rag_config JSONB,
                indexing_config JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, collection_name)
            );
            """

            indexes = """
            CREATE INDEX IF NOT EXISTS idx_user_collections_user_id ON user_collections(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_collections_collection_name ON user_collections(collection_name);
            """

            db_connection.execute_query(user_collections_table)
            db_connection.execute_query(indexes)

            logger.info("Collection schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize collection schema: {e}")

    def create_collection(
        self,
        user_id: str,
        collection_name: str,
        rag_config: Optional[Dict] = None,
        indexing_config: Optional[Dict] = None
    ) -> bool:
        try:
            query = """
            INSERT INTO user_collections (user_id, collection_name, rag_config, indexing_config)
            VALUES (%s, %s, %s, %s)
            """
            db_connection.execute_query(
                query,
                (
                    user_id,
                    collection_name,
                    json.dumps(rag_config) if rag_config else None,
                    json.dumps(indexing_config) if indexing_config else None
                )
            )
            logger.info(f"Created collection '{collection_name}' for user '{user_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def collection_exists(self, user_id: str, collection_name: str) -> bool:
        query = "SELECT id FROM user_collections WHERE user_id = %s AND collection_name = %s"
        result = db_connection.execute_one(query, (user_id, collection_name))
        return result is not None

    def get_collection(self, user_id: str, collection_name: str) -> Optional[Dict[str, Any]]:
        query = """
        SELECT id, user_id, collection_name, rag_config, indexing_config, created_at
        FROM user_collections
        WHERE user_id = %s AND collection_name = %s
        """
        result = db_connection.execute_one(query, (user_id, collection_name))
        if result:
            return {
                "id": str(result[0]),
                "user_id": result[1],
                "collection_name": result[2],
                "rag_config": result[3],
                "indexing_config": result[4],
                "created_at": result[5].isoformat() if result[5] else None
            }
        return None

    def list_collections(self, user_id: str) -> List[str]:
        query = "SELECT collection_name FROM user_collections WHERE user_id = %s ORDER BY created_at DESC"
        results = db_connection.execute_query(query, (user_id,))
        return [row[0] for row in results] if results else []

    def delete_collection(self, user_id: str, collection_name: str) -> bool:
        try:
            query = "DELETE FROM user_collections WHERE user_id = %s AND collection_name = %s"
            db_connection.execute_query(query, (user_id, collection_name))
            logger.info(f"Deleted collection '{collection_name}' for user '{user_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False


collection_repository = CollectionRepository()
