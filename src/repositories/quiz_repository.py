import logging
import json
from typing import Optional, Dict, Any, List
from database.postgres_connection import db_connection
from models.quiz_models import QuizResponse

logger = logging.getLogger(__name__)


class QuizRepository:
    def __init__(self):
        self.init_schema()

    def init_schema(self):
        try:
            quiz_table = """
            CREATE TABLE IF NOT EXISTS user_quizzes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL REFERENCES users(id),
                quiz_id VARCHAR(255) NOT NULL,
                collection_name VARCHAR(255) NOT NULL,
                title VARCHAR(500) NOT NULL,
                difficulty VARCHAR(50) NOT NULL,
                quiz_data JSONB NOT NULL,
                generation_metadata JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, quiz_id)
            );
            """

            indexes = """
            CREATE INDEX IF NOT EXISTS idx_user_quizzes_user_id ON user_quizzes(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_quizzes_collection_name ON user_quizzes(collection_name);
            CREATE INDEX IF NOT EXISTS idx_user_quizzes_created_at ON user_quizzes(created_at);
            """

            db_connection.execute_query(quiz_table)
            db_connection.execute_query(indexes)

            logger.info("Quiz schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize quiz schema: {e}")

    def save_quiz(self, user_id: str, quiz_response: QuizResponse) -> str:
        """Save quiz to database and return the database ID."""
        try:
            query = """
            INSERT INTO user_quizzes (user_id, quiz_id, collection_name, title, difficulty, quiz_data, generation_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, quiz_id) DO UPDATE SET
                quiz_data = EXCLUDED.quiz_data,
                generation_metadata = EXCLUDED.generation_metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """

            quiz_data_json = quiz_response.quiz_data.dict()
            generation_metadata_json = quiz_response.generation_metadata.dict()

            result = db_connection.execute_one(query, (
                user_id,
                quiz_response.quiz_data.quiz_metadata.quiz_id,
                quiz_response.quiz_data.quiz_metadata.source.collection_name,
                quiz_response.quiz_data.quiz_metadata.title,
                quiz_response.quiz_data.quiz_metadata.difficulty,
                json.dumps(quiz_data_json),
                json.dumps(generation_metadata_json)
            ))

            return str(result[0]) if result else None

        except Exception as e:
            logger.error(f"Failed to save quiz: {e}")
            raise

    def get_quiz_by_id(self, user_id: str, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz by quiz_id for a specific user."""
        try:
            query = """
            SELECT id, quiz_id, collection_name, title, difficulty, quiz_data, generation_metadata, created_at, updated_at
            FROM user_quizzes
            WHERE user_id = %s AND quiz_id = %s
            """
            result = db_connection.execute_one(query, (user_id, quiz_id))

            if result:
                return {
                    "id": str(result[0]),
                    "quiz_id": result[1],
                    "collection_name": result[2],
                    "title": result[3],
                    "difficulty": result[4],
                    "quiz_data": result[5],
                    "generation_metadata": result[6],
                    "created_at": result[7].isoformat() if result[7] else None,
                    "updated_at": result[8].isoformat() if result[8] else None
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get quiz by ID: {e}")
            raise

    def get_user_quizzes(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all quizzes for a user with pagination."""
        try:
            query = """
            SELECT id, quiz_id, collection_name, title, difficulty, created_at, updated_at
            FROM user_quizzes
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """
            results = db_connection.execute_query(query, (user_id, limit, offset))

            quizzes = []
            for result in results:
                quizzes.append({
                    "id": str(result[0]),
                    "quiz_id": result[1],
                    "collection_name": result[2],
                    "title": result[3],
                    "difficulty": result[4],
                    "created_at": result[5].isoformat() if result[5] else None,
                    "updated_at": result[6].isoformat() if result[6] else None
                })

            return quizzes

        except Exception as e:
            logger.error(f"Failed to get user quizzes: {e}")
            raise

    def get_collection_quizzes(self, user_id: str, collection_name: str) -> List[Dict[str, Any]]:
        """Get all quizzes for a user's specific collection."""
        try:
            query = """
            SELECT id, quiz_id, collection_name, title, difficulty, created_at, updated_at
            FROM user_quizzes
            WHERE user_id = %s AND collection_name = %s
            ORDER BY created_at DESC
            """
            results = db_connection.execute_query(query, (user_id, collection_name))

            quizzes = []
            for result in results:
                quizzes.append({
                    "id": str(result[0]),
                    "quiz_id": result[1],
                    "collection_name": result[2],
                    "title": result[3],
                    "difficulty": result[4],
                    "created_at": result[5].isoformat() if result[5] else None,
                    "updated_at": result[6].isoformat() if result[6] else None
                })

            return quizzes

        except Exception as e:
            logger.error(f"Failed to get collection quizzes: {e}")
            raise

    def delete_quiz(self, user_id: str, quiz_id: str) -> bool:
        """Delete a quiz for a specific user."""
        try:
            query = "DELETE FROM user_quizzes WHERE user_id = %s AND quiz_id = %s"
            rowcount = db_connection.execute_query(query, (user_id, quiz_id))
            return rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete quiz: {e}")
            raise

    def quiz_exists(self, user_id: str, quiz_id: str) -> bool:
        """Check if a quiz exists for a user."""
        try:
            query = "SELECT id FROM user_quizzes WHERE user_id = %s AND quiz_id = %s"
            result = db_connection.execute_one(query, (user_id, quiz_id))
            return result is not None

        except Exception as e:
            logger.error(f"Failed to check quiz existence: {e}")
            raise


quiz_repository = QuizRepository()