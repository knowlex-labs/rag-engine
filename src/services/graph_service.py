
import logging
from neo4j import GraphDatabase
from config import Config

logger = logging.getLogger(__name__)

class GraphService:
    def __init__(self):
        self._init_driver()

    def _init_driver(self):
        uri = Config.neo4j.URI
        user = Config.neo4j.USER
        password = Config.neo4j.PASSWORD
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.verify_connection()
            logger.info("Neo4j driver initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            self.driver = None

    def verify_connection(self):
        if self.driver:
            self.driver.verify_connectivity()

    def close(self):
        if self.driver:
            self.driver.close()

    def execute_query(self, query: str, parameters: dict = None, db: str = None):
        """Execute a Cypher query."""
        if not self.driver:
            logger.error("Neo4j driver is not initialized.")
            return None

        database = db or Config.neo4j.DATABASE
        try:
            records, summary, keys = self.driver.execute_query(
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

graph_service = GraphService()
