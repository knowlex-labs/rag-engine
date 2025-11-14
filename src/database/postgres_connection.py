import psycopg2
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self):
        self.conn = None
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = os.getenv("POSTGRES_PORT", "5432")
        self.database = os.getenv("POSTGRES_DB", "rag_engine")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "postgres")

    def connect(self):
        import time
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                logger.info(f"Connected to PostgreSQL at {self.host}:{self.port}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to PostgreSQL after {max_retries} attempts: {e}")
                    raise e

    def get_connection(self):
        if not self.conn or self.conn.closed:
            self.connect()
        return self.conn

    def execute_query(self, query: str, params: Optional[tuple] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def execute_one(self, query: str, params: Optional[tuple] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            # Commit non-SELECT queries
            if not query.strip().upper().startswith('SELECT'):
                conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


db_connection = DatabaseConnection()