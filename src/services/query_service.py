from typing import List, Dict, Any
from repositories.qdrant_repository import QdrantRepository
from repositories.feedback_repository import FeedbackRepository
from utils.embedding_client import EmbeddingClient
from utils.llm_client import LlmClient
from models.api_models import QueryResponse, ChunkConfig, CriticEvaluation
from core.reranker import reranker
from core.critic import critic
from config import Config

class QueryService:
    def __init__(self):
        self.qdrant_repo = QdrantRepository()
        self.embedding_client = EmbeddingClient()
        self.llm_client = LlmClient()
        self.feedback_repo = FeedbackRepository()

    def _filter_relevant_results(self, results: List[Dict], threshold: float = 0.5) -> List[Dict]:
        return [result for result in results if result.get("score", 0) >= threshold]

    def _is_valid_text(self, text: str) -> bool:
        if not text or len(text.strip()) == 0:
            return False
        printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
        return (printable_chars / len(text)) > 0.8

    def _extract_relevant_chunks(self, results: List[Dict]) -> List[ChunkConfig]:
        if not results:
            return []

        chunks = []
        seen_texts = set()

        for result in results:
            payload = result.get("payload", {})
            text = payload.get("text", "")
            source = payload.get("document_id", "unknown")

            if text and self._is_valid_text(text) and text not in seen_texts:
                seen_texts.add(text)
                chunks.append(ChunkConfig(source=source, text=text))

        return chunks[:3]

    def _extract_full_texts(self, results: List[Dict]) -> List[str]:
        full_texts = []
        seen_texts = set()

        for result in results:
            payload = result.get("payload", {})
            text = payload.get("text", "")

            if text and self._is_valid_text(text) and text not in seen_texts:
                seen_texts.add(text)
                full_texts.append(text)

        return full_texts[:3]

    def _calculate_confidence(self, results: List[Dict]) -> float:
        if not results:
            return 0.0
        return max(result.get("score", 0) for result in results)

    def _create_query_response(self, results: List[Dict], query: str, enable_critic: bool = True) -> QueryResponse:
        relevant_results = self._filter_relevant_results(results)

        if not relevant_results:
            return QueryResponse(
                answer="Context not found",
                confidence=0.0,
                is_relevant=False,
                chunks=[]
            )

        chunks = self._extract_relevant_chunks(relevant_results)

        if not chunks:
            return QueryResponse(
                answer="Error: Stored content is corrupted or unreadable",
                confidence=0.0,
                is_relevant=False,
                chunks=[]
            )

        chunk_texts = [chunk.text for chunk in chunks]
        full_chunk_texts = self._extract_full_texts(relevant_results)
        answer = self.llm_client.generate_answer(query, chunk_texts)
        confidence = self._calculate_confidence(relevant_results)

        critic_result = None
        if enable_critic and critic.is_available():
            if critic_evaluation := critic.evaluate(query, full_chunk_texts, answer):
                critic_result = CriticEvaluation(**critic_evaluation)

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            is_relevant=True,
            chunks=chunks,
            critic=critic_result
        )

    def _apply_feedback_scoring(self, results: List[Dict], query_vector: List[float],
                              collection_name: str) -> List[Dict]:
        if not Config.feedback.FEEDBACK_ENABLED or not results:
            return results

        try:
            relevant_feedback = self.feedback_repo.get_relevant_feedback(
                query_vector, collection_name, Config.feedback.FEEDBACK_SIMILARITY_THRESHOLD
            )

            if not relevant_feedback:
                return results

            doc_ids = [result.get("payload", {}).get("document_id", "") for result in results]
            feedback_scores = self.feedback_repo.calculate_feedback_scores(doc_ids, relevant_feedback)

            for result in results:
                doc_id = result.get("payload", {}).get("document_id", "")
                original_score = result.get("score", 0.0)
                rerank_score = result.get("rerank_score", original_score)
                feedback_score = feedback_scores.get(doc_id, 0.5)

                final_score = (0.45 * original_score + 0.35 * rerank_score +
                             0.10 * feedback_score + 0.10 * feedback_score)

                result["score"] = final_score
                result["feedback_score"] = feedback_score

            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return results

        except Exception:
            return results

    def search(self, collection_name: str, query_text: str, limit: int = 10, enable_critic: bool = True) -> QueryResponse:
        try:
            query_vector = self.embedding_client.generate_single_embedding(query_text)
            results = self.qdrant_repo.query_collection(collection_name, query_vector, limit)

            # Apply reranking if available and enabled
            if reranker.is_available() and results:
                results = reranker.rerank(query_text, results)

            # Apply feedback scoring if enabled
            results = self._apply_feedback_scoring(results, query_vector, collection_name)

            return self._create_query_response(results, query_text, enable_critic)
        except Exception as e:
            return QueryResponse(
                answer="Context not found",
                confidence=0.0,
                is_relevant=False,
                chunks=[]
            )