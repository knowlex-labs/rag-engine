import logging
from typing import List, Dict, Any, Optional
from config import Config
from services.graph_service import get_graph_service

logger = logging.getLogger(__name__)

class Neo4jRepository:
    def __init__(self):
        # Use lazy initialization - graph service will be created when first accessed
        self._graph_service = None

    @property
    def graph_service(self):
        if self._graph_service is None:
            self._graph_service = get_graph_service()
            self._ensure_indexes()
        return self._graph_service

    def _ensure_indexes(self):
        try:
            vector_dim = 1536 if Config.embedding.PROVIDER == "openai" else Config.embedding.VECTOR_SIZE

            query = f"""
            CREATE VECTOR INDEX {Config.neo4j.VECTOR_INDEX_NAME} IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {{
                indexConfig: {{
                    `vector.dimensions`: {vector_dim},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
            """
            self.graph_service.execute_query(query)
            logger.info(f"Vector index '{Config.neo4j.VECTOR_INDEX_NAME}' ensured ({vector_dim}D)")

            property_indexes = [
                "CREATE INDEX chunk_file_id_idx IF NOT EXISTS FOR (c:Chunk) ON (c.file_id)",
                "CREATE INDEX chunk_collection_id_idx IF NOT EXISTS FOR (c:Chunk) ON (c.collection_id)",
                "CREATE INDEX chunk_type_idx IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_type)",
                # Note: document_file_id_idx removed - the constraint below will create its backing index
                "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
                "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.file_id IS UNIQUE"
            ]

            for index_query in property_indexes:
                self.graph_service.execute_query(index_query)

            logger.info("Property indexes and constraints created")

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

    def create_user_collection(self, user_id: str, collection_id: str) -> bool:
        try:
            query = """
            MERGE (u:User {user_id: $user_id})
            MERGE (c:Collection {collection_id: $collection_id})
            MERGE (u)-[:OWNS]->(c)
            RETURN c.collection_id as collection_id
            """
            result = self.graph_service.execute_query(
                query,
                {"user_id": user_id, "collection_id": collection_id}
            )
            logger.info(f"Collection {collection_id} created for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return False

    def index_chunks(
        self,
        chunks: List[Any],
        embeddings: List[List[float]],
        user_id: str,
        collection_id: str,
        file_id: str,
        file_name: str,
        source_type: str
    ) -> bool:
        try:
            query = """
            MERGE (u:User {user_id: $user_id})
            MERGE (col:Collection {collection_id: $collection_id})
            MERGE (u)-[:OWNS]->(col)

            MERGE (d:Document {file_id: $file_id})
            SET d.file_name = $file_name,
                d.source_type = $source_type,
                d.indexed_at = datetime()
            MERGE (col)-[:CONTAINS]->(d)

            WITH d
            UNWIND $chunks_data as chunk_data

            MERGE (c:Chunk {chunk_id: chunk_data.chunk_id})
            SET c.chunk_id = chunk_data.chunk_id,
                c.text = chunk_data.text,
                c.embedding = chunk_data.embedding,
                c.file_id = $file_id,
                c.collection_id = $collection_id,
                c.chunk_type = chunk_data.chunk_type,
                c.chapter_title = chunk_data.chapter_title,
                c.section_title = chunk_data.section_title,
                c.page_start = chunk_data.page_start,
                c.page_end = chunk_data.page_end,
                c.key_terms = chunk_data.key_terms,
                c.has_equations = chunk_data.has_equations,
                c.has_diagrams = chunk_data.has_diagrams,
                c.indexed_at = datetime()

            MERGE (d)-[:HAS_CHUNK]->(c)

            RETURN count(c) as chunks_created
            """

            chunks_data = []
            for i, chunk in enumerate(chunks):
                chunks_data.append({
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "embedding": embeddings[i],
                    "chunk_type": chunk.chunk_metadata.chunk_type.value,
                    "chapter_title": chunk.topic_metadata.chapter_title,
                    "section_title": chunk.topic_metadata.section_title,
                    "page_start": chunk.topic_metadata.page_start,
                    "page_end": chunk.topic_metadata.page_end,
                    "key_terms": chunk.chunk_metadata.key_terms,
                    "has_equations": chunk.chunk_metadata.has_equations,
                    "has_diagrams": chunk.chunk_metadata.has_diagrams
                })

            result = self.graph_service.execute_query(
                query,
                {
                    "user_id": user_id,
                    "collection_id": collection_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "source_type": source_type,
                    "chunks_data": chunks_data
                }
            )

            logger.info(f"Indexed {len(chunks)} chunks for file {file_id}")
            return True

        except Exception as e:
            logger.error(f"Error indexing chunks: {e}")
            raise

    def index_legal_entities(
        self,
        file_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> bool:
        try:
            for node in nodes:
                node_query = f"""
                MERGE (n:{node['label']} {{id: $id}})
                SET n.text = $text,
                    n.file_id = $file_id
                """
                self.graph_service.execute_query(
                    node_query,
                    {
                        "id": f"{file_id}_{node['id']}",
                        "text": node.get('text', ''),
                        "file_id": file_id
                    }
                )

            for edge in edges:
                edge_query = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[:{edge['label']}]->(target)
                """
                self.graph_service.execute_query(
                    edge_query,
                    {
                        "source_id": f"{file_id}_{edge['source']}",
                        "target_id": f"{file_id}_{edge['target']}"
                    }
                )

            logger.info(f"Indexed {len(nodes)} entities and {len(edges)} relationships for file {file_id}")
            return True

        except Exception as e:
            logger.error(f"Error indexing legal entities: {e}")
            return False

    def link_chunks_to_entities(
        self,
        chunk_id: str,
        entity_ids: List[str]
    ) -> bool:
        try:
            query = """
            MATCH (c:Chunk {chunk_id: $chunk_id})
            UNWIND $entity_ids as entity_id
            MATCH (e {id: entity_id})
            MERGE (c)-[:MENTIONS]->(e)
            RETURN count(*) as links_created
            """
            self.graph_service.execute_query(
                query,
                {"chunk_id": chunk_id, "entity_ids": entity_ids}
            )
            return True
        except Exception as e:
            logger.error(f"Error linking chunks to entities: {e}")
            return False

    def delete_file(self, user_id: str, file_id: str) -> bool:
        try:
            query = """
            MATCH (d:Document {file_id: $file_id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            OPTIONAL MATCH (c)-[:MENTIONS]->(e)
            WHERE e.file_id = $file_id
            DETACH DELETE c, e, d
            RETURN count(*) as deleted_count
            """
            result = self.graph_service.execute_query(
                query,
                {"file_id": file_id}
            )
            logger.info(f"Deleted file {file_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def delete_collection(self, user_id: str, collection_id: str) -> bool:
        try:
            query = """
            MATCH (col:Collection {collection_id: $collection_id})
            OPTIONAL MATCH (col)-[:CONTAINS]->(d:Document)
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            OPTIONAL MATCH (c)-[:MENTIONS]->(e)
            WHERE e IS NULL OR e.file_id = d.file_id
            DETACH DELETE col, d, c, e
            RETURN count(*) as deleted_count
            """
            result = self.graph_service.execute_query(
                query,
                {"collection_id": collection_id}
            )
            logger.info(f"Deleted collection {collection_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False

    def vector_search(
        self,
        query_embedding: List[float],
        collection_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            where_clauses = []
            params = {
                "query_embedding": query_embedding,
                "top_k": top_k
            }

            if collection_ids:
                where_clauses.append("c.collection_id IN $collection_ids")
                params["collection_ids"] = collection_ids

            if file_ids:
                where_clauses.append("c.file_id IN $file_ids")
                params["file_ids"] = file_ids

            where_clause = " AND " + " AND ".join(where_clauses) if where_clauses else ""

            query = f"""
            CALL db.index.vector.queryNodes(
                '{Config.neo4j.VECTOR_INDEX_NAME}',
                $top_k,
                $query_embedding
            ) YIELD node as c, score
            WHERE 1=1{where_clause}
            RETURN c.chunk_id as chunk_id,
                   c.text as text,
                   c.file_id as file_id,
                   c.collection_id as collection_id,
                   c.chunk_type as chunk_type,
                   c.chapter_title as chapter_title,
                   c.section_title as section_title,
                   CASE WHEN c.page_start IS NOT NULL THEN c.page_start ELSE null END as page_start,
                   CASE WHEN c.page_end IS NOT NULL THEN c.page_end ELSE null END as page_end,
                   c.key_terms as key_terms,
                   score
            ORDER BY score DESC
            LIMIT $top_k
            """

            results = self.graph_service.execute_query(query, params)

            return [dict(record) for record in results]

        except Exception as e:
            logger.error(f"Error performing vector search: {e}")
            return []

neo4j_repository = Neo4jRepository()
