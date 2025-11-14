from typing import List, Dict, Any, Optional
from repositories.qdrant_repository import QdrantRepository
from repositories.feedback_repository import FeedbackRepository
from utils.embedding_client import EmbeddingClient
from utils.llm_client import LlmClient
from utils.response_enhancer import enhance_response_if_needed
from models.api_models import QueryResponse, ChunkConfig, CriticEvaluation, ChunkType, QuizConfig
from models.quiz_models import QuizResponse
from services.quiz_mapper_service import QuizMapperService
from core.reranker import reranker
from core.critic import critic
from config import Config
import re
import time
import logging

logger = logging.getLogger(__name__)

class QueryService:
    def __init__(self):
        self.qdrant_repo = QdrantRepository()
        self.embedding_client = EmbeddingClient()
        self.llm_client = LlmClient()
        self.feedback_repo = FeedbackRepository()
        self.quiz_mapper = QuizMapperService()

        # Patterns for detecting query intent
        self.concept_patterns = [
            r'^what (is|are|does|do)',
            r'^explain',
            r'^define',
            r'^describe',
            r'definition of',
            r'meaning of',
            r'concept of',
            r'understanding',
            r'tell me about'
        ]
        self.example_patterns = [
            r'example',
            r'show me',
            r'demonstrate',
            r'illustration',
            r'sample',
            r'case study'
        ]
        self.question_patterns = [
            r'^how (do|to|can)',
            r'^solve',
            r'^calculate',
            r'^find',
            r'^determine',
            r'practice',
            r'exercise',
            r'problem'
        ]

    def _detect_query_intent(self, query: str) -> Optional[str]:
        """
        Detect the intent of a query to determine which chunk type to prioritize.

        Returns:
            'concept', 'example', 'question', or None for mixed search
        """
        query_lower = query.lower().strip()

        # Check for concept queries
        for pattern in self.concept_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return ChunkType.CONCEPT.value

        # Check for example queries
        for pattern in self.example_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return ChunkType.EXAMPLE.value

        # Check for question/problem queries
        for pattern in self.question_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return ChunkType.QUESTION.value

        return None  # No specific intent, search all types

    def _smart_chunk_retrieval(
        self,
        collection_name: str,
        query_vector: List[float],
        query_text: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Intelligently retrieve chunks based on query intent.

        For concept queries: Prioritize concepts, then examples
        For example queries: Prioritize examples, then concepts
        For problem queries: Prioritize questions and examples
        For general queries: Mix all types
        """
        intent = self._detect_query_intent(query_text)

        if not intent:
            # No specific intent - get diverse results
            return self.qdrant_repo.query_collection(collection_name, query_vector, limit)

        # Get chunks of the prioritized type
        primary_results = self.qdrant_repo.query_collection(
            collection_name, query_vector, limit=limit//2, chunk_type=intent
        )

        # Get supporting chunks based on intent
        if intent == ChunkType.CONCEPT.value:
            # For concept queries, also get examples to illustrate
            secondary_results = self.qdrant_repo.query_collection(
                collection_name, query_vector, limit=limit//2, chunk_type=ChunkType.EXAMPLE.value
            )
        elif intent == ChunkType.EXAMPLE.value:
            # For example queries, also get concepts for context
            secondary_results = self.qdrant_repo.query_collection(
                collection_name, query_vector, limit=limit//2, chunk_type=ChunkType.CONCEPT.value
            )
        elif intent == ChunkType.QUESTION.value:
            # For problem queries, get examples showing solutions
            secondary_results = self.qdrant_repo.query_collection(
                collection_name, query_vector, limit=limit//2, chunk_type=ChunkType.EXAMPLE.value
            )
        else:
            secondary_results = []

        # Combine and sort by relevance
        combined = primary_results + secondary_results
        combined.sort(key=lambda x: x.get("score", 0), reverse=True)
        return combined[:limit]

    def _filter_relevant_results(self, results: List[Dict], threshold: float = None) -> List[Dict]:
        if threshold is None:
            threshold = Config.query.RELEVANCE_THRESHOLD
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

        return chunks[:5]  # Increased for better quiz generation context

    def _extract_full_texts(self, results: List[Dict]) -> List[str]:
        full_texts = []
        seen_texts = set()

        for result in results:
            payload = result.get("payload", {})
            text = payload.get("text", "")

            if text and self._is_valid_text(text) and text not in seen_texts:
                seen_texts.add(text)
                full_texts.append(text)

        return full_texts[:5]  # Increased for better context

    def _calculate_confidence(self, results: List[Dict]) -> float:
        if not results:
            return 0.0
        return max(result.get("score", 0) for result in results)

    def _create_query_response(self, results: List[Dict], query: str, enable_critic: bool = True, structured_output: bool = False) -> QueryResponse:
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
        answer = self.llm_client.generate_answer(query, chunk_texts, force_json=structured_output)
        answer = enhance_response_if_needed(answer, query)

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

    def _create_quiz_response(self, results: List[Dict], query: str, quiz_config: QuizConfig, collection_name: str, start_time: float) -> QuizResponse:
        """Create quiz response using the quiz mapper service."""
        relevant_results = self._filter_relevant_results(results)

        if not relevant_results:
            return self._create_error_quiz_response("Context not found")

        chunks = self._extract_relevant_chunks(relevant_results)

        if not chunks:
            return self._create_error_quiz_response("Error: Stored content is corrupted or unreadable")

        chunk_texts = [chunk.text for chunk in chunks]

        enhanced_query = self._enhance_quiz_query(query, chunk_texts, quiz_config)

        llm_response = self.llm_client.generate_answer(enhanced_query, chunk_texts, force_json=True, quiz_config=quiz_config)

        generation_time_ms = int((time.time() - start_time) * 1000)

        query_metadata = {
            "confidence": self._calculate_confidence(relevant_results),
            "is_relevant": True,
            "model_used": self.llm_client.provider
        }

        return self.quiz_mapper.transform_llm_to_frontend(
            llm_response=llm_response,
            quiz_config=quiz_config,
            query_metadata=query_metadata,
            context_chunks=chunks,
            generation_time_ms=generation_time_ms
        )

    def _create_error_quiz_response(self, error_message: str) -> QuizResponse:
        """Create a default quiz response structure for errors."""
        from models.quiz_models import (
            QuizData, QuizMetadata, QuizSource, ContentSummary,
            ScoringInfo, GenerationMetadata
        )

        # Create minimal error response structure
        quiz_metadata = QuizMetadata(
            quiz_id="error",
            title="Quiz Generation Error",
            difficulty="unknown",
            estimated_time_minutes=0,
            total_questions=0,
            max_score=0,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            source=QuizSource(type="collection", collection_name="unknown", source_count=0)
        )

        content_summary = ContentSummary(
            main_summary=f"Error: {error_message}",
            key_concepts=[],
            topics_covered=[],
            prerequisite_knowledge=[]
        )

        scoring_info = ScoringInfo(
            total_score=0,
            passing_score=0,
            time_limit_minutes=0
        )

        generation_metadata = GenerationMetadata(
            confidence=0.0,
            is_relevant=False,
            generation_time_ms=0,
            model_used="unknown",
            content_sources=[]
        )

        quiz_data = QuizData(
            quiz_metadata=quiz_metadata,
            questions=[],
            content_summary=content_summary,
            scoring_info=scoring_info
        )

        return QuizResponse(
            quiz_data=quiz_data,
            generation_metadata=generation_metadata
        )

    def _enhance_quiz_query(self, query: str, chunk_texts: List[str], quiz_config: QuizConfig) -> str:
        """Enhance quiz queries with specific topic information from content and quiz config details."""

        topics = self._extract_topics_from_content(chunk_texts)
        collection_name = quiz_config.collection_name.replace('_', ' ').title()

        if topics:
            topic_list = ', '.join(topics[:3])
            enhanced_query = f"Generate {quiz_config.num_questions} {quiz_config.difficulty} level quiz questions about {topic_list} from {collection_name} collection. Original request: {query}"
        else:
            enhanced_query = f"Generate {quiz_config.num_questions} {quiz_config.difficulty} level quiz questions from {collection_name} collection based on the provided content. Original request: {query}"

        return enhanced_query

    def _extract_topics_from_content(self, chunk_texts: List[str]) -> List[str]:
        """Extract physics topics from content chunks."""

        physics_topics = {
            'newton': "Newton's Laws",
            'motion': "Motion and Kinematics",
            'force': "Forces",
            'energy': "Energy",
            'momentum': "Momentum",
            'gravity': "Gravity",
            'friction': "Friction",
            'waves': "Waves",
            'thermodynamics': "Thermodynamics",
            'heat': "Heat Transfer",
            'electricity': "Electricity",
            'magnetism': "Magnetism",
            'optics': "Optics",
            'light': "Light and Optics",
            'quantum': "Quantum Physics",
            'relativity': "Relativity",
            'mechanics': "Classical Mechanics",
            'equilibrium': "Equilibrium",
            'acceleration': "Acceleration",
            'velocity': "Velocity",
            'pressure': "Pressure",
            'circuit': "Electric Circuits",
            'magnetic field': "Magnetic Fields",
            'electric field': "Electric Fields",
            'work': "Work and Power",
            'power': "Power",
            'oscillation': "Oscillations",
            'pendulum': "Pendulum Motion",
            'fluid': "Fluid Mechanics",
            'gas': "Gas Laws",
            'atomic': "Atomic Physics",
            'nuclear': "Nuclear Physics"
        }

        content = ' '.join(chunk_texts).lower()
        found_topics = []

        for keyword, topic in physics_topics.items():
            if keyword in content and topic not in found_topics:
                found_topics.append(topic)

        return found_topics

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

    def search(self, collection_name: str, query_text: str, limit: int = 10, enable_critic: bool = True, structured_output: bool = False, quiz_config: Optional[QuizConfig] = None):
        """
        Search with smart chunking - automatically detects query intent and retrieves
        appropriate chunk types (concepts, examples, or questions).

        Returns QuizResponse if quiz_config is provided, otherwise QueryResponse.
        """
        start_time = time.time()

        try:
            # Generate embedding
            query_vector = self.embedding_client.generate_single_embedding(query_text)

            # Use smart retrieval to get relevant chunks based on query intent
            results = self._smart_chunk_retrieval(collection_name, query_vector, query_text, limit)

            # Apply reranking if available and enabled
            if reranker.is_available() and results:
                results = reranker.rerank(query_text, results)

            # Apply feedback scoring if enabled
            results = self._apply_feedback_scoring(results, query_vector, collection_name)

            # Quiz mode vs regular mode
            if quiz_config is not None:
                return self._create_quiz_response(results, query_text, quiz_config, collection_name, start_time)
            else:
                return self._create_query_response(results, query_text, enable_critic, structured_output)
        except Exception as e:
            logger.error(f"Error in query search: {str(e)}")
            if quiz_config is not None:
                # Return a default quiz response structure for errors
                return self._create_error_quiz_response(str(e))
            else:
                return QueryResponse(
                    answer="Context not found",
                    confidence=0.0,
                    is_relevant=False,
                    chunks=[]
                )