
import logging
import threading
from neo4j import GraphDatabase
from config import Config

logger = logging.getLogger(__name__)

class GraphService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GraphService, cls).__new__(cls)
                    cls._instance._driver = None
                    cls._instance._initialized = False
        return cls._instance

    def _init_driver(self):
        """Initialize Neo4j driver - called lazily on first use."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            uri = Config.neo4j.URI
            user = Config.neo4j.USER
            password = Config.neo4j.PASSWORD

            try:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                self.verify_connection()
                logger.info("Neo4j driver initialized successfully.")
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j driver: {e}")
                self._driver = None
                self._initialized = False
                raise e

    def _ensure_driver(self):
        """Ensure driver is initialized before use."""
        if not self._initialized:
            self._init_driver()
        return self._driver

    def verify_connection(self):
        if self._driver:
            self._driver.verify_connectivity()

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
            self._initialized = False

    def execute_query(self, query: str, parameters: dict = None, db: str = None):
        """Execute a Cypher query."""
        driver = self._ensure_driver()
        if not driver:
            logger.error("Neo4j driver is not initialized.")
            return None

        database = db or Config.neo4j.DATABASE
        try:
            records, summary, keys = driver.execute_query(
                query,
                parameters_=parameters,
                database_=database
            )
            return records
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise e

    def flush_database(self):
        """Dangerous: Clears the entire database."""
        query = "MATCH (n) DETACH DELETE n"
        self.execute_query(query)

def get_graph_service():
    """Get the singleton GraphService instance."""
    return GraphService()
