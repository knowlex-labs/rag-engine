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
        import time
        start_time = time.time()
        
        question = request.question
        max_chunks = 5
        scope = getattr(request, 'scope', [])  # Default to empty (search all)
        answer_style = getattr(request, 'answer_style', 'student_friendly')
        logger.info(f"Legal query: {question[:100]}, scope: {scope}")

        try:
            # Map scope to collection IDs
            collection_ids = []
            actual_scope = []

            if not scope:
                # No filter provided - search ALL collections
                collection_ids = ['constitution-golden-source', 'bns-golden-source']
                actual_scope = ['all']
            else:
                # Use provided filters
                for doc_type in scope:
                    # Extract the value from the enum
                    doc_type_value = doc_type.value if hasattr(doc_type, 'value') else str(doc_type)
                    
                    if doc_type_value == 'constitution':
                        collection_ids.append('constitution-golden-source')
                        actual_scope.append('constitution')
                    elif doc_type_value == 'bns':
                        collection_ids.append('bns-golden-source')
                        actual_scope.append('bns')
                    elif doc_type_value == 'all':
                        collection_ids.extend(['constitution-golden-source', 'bns-golden-source'])
                        actual_scope.append('all')

                # Remove duplicates
                collection_ids = list(set(collection_ids))
                actual_scope = list(set(actual_scope))

            logger.info(f"Searching collections: {collection_ids}")
            logger.info(f"Actual scope for response: {actual_scope}")

            chunks = self._get_multi_collection_chunks(question, max_chunks, collection_ids)
            logger.info(f"Found {len(chunks)} constitutional chunks")

            processing_time_ms = int((time.time() - start_time) * 1000)
            
            if not chunks:
                # Create dynamic error message based on scope
                if 'bns' in actual_scope and 'constitution' not in actual_scope:
                    no_content_msg = "No BNS content found for your question."
                elif 'constitution' in actual_scope and 'bns' not in actual_scope:
                    no_content_msg = "No constitutional content found for your question."
                else:
                    no_content_msg = "No legal content found for your question."

                return {
                    "answer": no_content_msg,
                    "question": question,
                    "sources": [],
                    "total_chunks_found": 0,
                    "chunks_used": 0,
                    "answer_style": answer_style,
                    "documents_searched": actual_scope,
                    "processing_time_ms": processing_time_ms
                }

            context_texts = [chunk['text'] for chunk in chunks]
            answer = self.llm_client.generate_answer(question, context_texts)

            # Simplified sources - just return empty for now to avoid validation errors
            sources = []
            
            processing_time_ms = int((time.time() - start_time) * 1000)

            return {
                "answer": answer,
                "question": question,
                "sources": sources,
                "total_chunks_found": len(chunks),
                "chunks_used": min(len(chunks), 3),
                "answer_style": answer_style,
                "documents_searched": actual_scope,
                "processing_time_ms": processing_time_ms
            }

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Legal query failed: {e}")
            return {
                "answer": "Error processing your legal query.",
                "question": question,
                "sources": [],
                "total_chunks_found": 0,
                "chunks_used": 0,
                "answer_style": answer_style if 'answer_style' in locals() else 'student_friendly',
                "documents_searched": actual_scope if 'actual_scope' in locals() else ['all'],
                "processing_time_ms": processing_time_ms
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
            # Log the ACTUAL exception type and traceback for debugging
            import traceback
            logger.error(f"Multi-collection Neo4j query failed: {type(e).__name__}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def _get_constitutional_chunks(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Legacy method - now calls multi-collection with constitution only"""
        return self._get_multi_collection_chunks(query, limit, ['constitution-golden-source'])