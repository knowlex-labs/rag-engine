from typing import List
from repositories.feedback_repository import FeedbackRepository
from utils.embedding_client import EmbeddingClient
from config import Config


class FeedbackService:
    def __init__(self):
        self.feedback_repo = FeedbackRepository()
        self.embedding_client = EmbeddingClient()

    def save_feedback(self, query: str, doc_ids: List[str], label: int, collection: str) -> bool:
        if not Config.feedback.FEEDBACK_ENABLED:
            return False

        if label not in [0, 1]:
            return False

        try:
            query_vector = self.embedding_client.generate_single_embedding(query)
            return self.feedback_repo.save_feedback(
                query=query,
                query_vector=query_vector,
                doc_ids=doc_ids,
                label=label,
                collection=collection
            )
        except Exception:
            return False

    def get_feedback_stats(self, collection: str = None):
        return self.feedback_repo.get_feedback_stats(collection)