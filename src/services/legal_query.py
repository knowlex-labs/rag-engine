import logging
from typing import List, Dict, Any
from repositories.neo4j_repository import Neo4jRepository
from utils.llm_client import LlmClient
from models.law_query_models import LawQueryRequest, LawQueryResponse, LegalDocumentType, LegalSourceReference, ConfidenceMetrics

logger = logging.getLogger(__name__)

class LegalQueryService:
    def __init__(self):
        self.neo4j_repo = Neo4jRepository()
        self.llm_client = LlmClient()

    async def process_legal_query(self, request, user_id: str) -> Dict[str, Any]:
        question = request.question
        max_chunks = 5
        scope = getattr(request, 'scope', [])  # Default to empty (search all)
        logger.info(f"Legal query: {question[:100]}, scope: {scope}")

        try:
            # Map scope to collection IDs
            collection_ids = []

            if not scope:
                # No filter provided - search ALL collections
                collection_ids = ['constitution-golden-source', 'bns-golden-source']
                actual_scope = ['all']
            else:
                # Use provided filters
                for doc_type in scope:
                    if str(doc_type) == 'constitution':
                        collection_ids.append('constitution-golden-source')
                    elif str(doc_type) == 'bns':
                        collection_ids.append('bns-golden-source')
                    elif str(doc_type) == 'all':
                        collection_ids.extend(['constitution-golden-source', 'bns-golden-source'])

                # Remove duplicates and set actual scope
                collection_ids = list(set(collection_ids))
                actual_scope = [str(s) for s in scope]

            logger.info(f"Searching collections: {collection_ids}")

            chunks = self._get_multi_collection_chunks(question, max_chunks, collection_ids)
            logger.info(f"Found {len(chunks)} constitutional chunks")

            if not chunks:
                return {
                    "answer": "No constitutional content found for your question.",
                    "question": question,
                    "sources": [],
                    "total_chunks_found": 0,
                    "chunks_used": 0
                }

            context_texts = [chunk['text'] for chunk in chunks]
            answer = self.llm_client.generate_answer(question, context_texts)

            sources = [{"text": chunk['text'][:200], "article": chunk.get('article', 'Unknown')} for chunk in chunks[:3]]

            return {
                "answer": answer,
                "question": question,
                "sources": sources,
                "total_chunks_found": len(chunks),
                "chunks_used": min(len(chunks), 3)
            }

        except Exception as e:
            logger.error(f"Legal query failed: {e}")
            return {
                "answer": "Error processing your legal query.",
                "question": question,
                "sources": [],
                "total_chunks_found": 0,
                "chunks_used": 0
            }

    def _get_multi_collection_chunks(self, query: str, limit: int, collection_ids: List[str]) -> List[Dict[str, Any]]:
        """Get chunks from multiple collections"""
        if not collection_ids:
            return []

        cypher = """
        CALL db.index.vector.queryNodes('legal_chunks_index', $limit, $query_embedding)
        YIELD node as c, score
        WHERE c.collection_id IN $collection_ids
        RETURN c.text as text, c.chunk_id as chunk_id, c.section_title as article, score
        ORDER BY score DESC LIMIT $limit
        """

        try:
            from utils.embedding_client import EmbeddingClient
            embedding_client = EmbeddingClient()
            query_embedding = embedding_client.generate_single_embedding(query)

            records = self.neo4j_repo.graph_service.execute_query(cypher, {
                'query_embedding': query_embedding,
                'collection_ids': collection_ids,
                'limit': limit
            })

            return [dict(record) for record in records]

        except Exception as e:
            logger.error(f"Multi-collection Neo4j query failed: {e}")
            return []

    def _get_constitutional_chunks(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Legacy method - now calls multi-collection with constitution only"""
        return self._get_multi_collection_chunks(query, limit, ['constitution-golden-source'])