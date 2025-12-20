import logging
from typing import List, Dict, Any
from repositories.neo4j_repository import Neo4jRepository
from utils.llm_client import LlmClient

logger = logging.getLogger(__name__)

class LegalQueryService:
    def __init__(self):
        self.neo4j_repo = Neo4jRepository()
        self.llm_client = LlmClient()

    def query_constitutional_law(self, question: str, user_id: str, max_chunks: int = 5) -> Dict[str, Any]:
        logger.info(f"Legal query: {question[:100]}...")

        try:
            chunks = self._get_constitutional_chunks(question, max_chunks)
            logger.info(f"Found {len(chunks)} constitutional chunks")

            if not chunks:
                return {
                    "answer": "No constitutional content found for your question.",
                    "sources": [],
                    "total_chunks": 0
                }

            context_texts = [chunk['text'] for chunk in chunks]
            answer = self.llm_client.generate_answer(question, context_texts)

            sources = [{"text": chunk['text'][:200], "article": chunk.get('article', 'Unknown')} for chunk in chunks[:3]]

            return {
                "answer": answer,
                "sources": sources,
                "total_chunks": len(chunks)
            }

        except Exception as e:
            logger.error(f"Legal query failed: {e}")
            return {
                "answer": "Error processing your legal query.",
                "sources": [],
                "total_chunks": 0
            }

    def _get_constitutional_chunks(self, query: str, limit: int) -> List[Dict[str, Any]]:
        cypher = """
        CALL db.index.vector.queryNodes('legal_chunks_index', $limit, $query_embedding)
        YIELD node as c, score
        WHERE c.collection_id = 'constitution-golden-source'
        RETURN c.text as text, c.chunk_id as chunk_id, c.section_title as article, score
        ORDER BY score DESC LIMIT $limit
        """

        try:
            from utils.embedding_client import EmbeddingClient
            embedding_client = EmbeddingClient()
            query_embedding = embedding_client.generate_single_embedding(query)

            records = self.neo4j_repo.graph_service.execute_query(cypher, {
                'query_embedding': query_embedding,
                'limit': limit
            })

            return [dict(record) for record in records]

        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return []