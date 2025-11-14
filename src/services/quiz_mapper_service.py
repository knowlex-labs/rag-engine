import json
import uuid
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from models.quiz_models import (
    QuizResponse, QuizData, QuizMetadata, QuizSource, QuizQuestion,
    QuestionConfig, AnswerConfig, QuestionContext, ContentSummary,
    ScoringInfo, GenerationMetadata, ContentSource
)
from models.api_models import QuizConfig, ChunkConfig
import logging

logger = logging.getLogger(__name__)

class QuizMapperService:
    """
    Service to transform raw LLM JSON response + quiz config into structured frontend format.
    Handles all business logic for quiz generation including topic extraction, ID generation,
    and metadata creation.
    """

    # Physics topic keywords for classification
    PHYSICS_TOPICS = {
        "newton": "Newton's Laws",
        "motion": "Motion and Kinematics",
        "force": "Forces",
        "energy": "Energy",
        "momentum": "Momentum",
        "gravity": "Gravity",
        "friction": "Friction",
        "waves": "Waves",
        "thermodynamics": "Thermodynamics",
        "electricity": "Electricity",
        "magnetism": "Magnetism",
        "optics": "Optics",
        "quantum": "Quantum Physics",
        "relativity": "Relativity",
        "mechanics": "Classical Mechanics",
        "equilibrium": "Equilibrium",
        "acceleration": "Acceleration",
        "velocity": "Velocity"
    }

    def __init__(self):
        self.logger = logger

    def transform_llm_to_frontend(
        self,
        llm_response: str,
        quiz_config: QuizConfig,
        query_metadata: Dict[str, Any],
        context_chunks: List[ChunkConfig],
        generation_time_ms: int
    ) -> QuizResponse:
        """
        Main transformation method that converts raw LLM JSON + quiz config
        into structured frontend format.

        Args:
            llm_response: Raw JSON string from LLM
            quiz_config: Quiz configuration from UI
            query_metadata: Metadata about the query (confidence, etc.)
            context_chunks: Source chunks used for generation
            generation_time_ms: Time taken to generate the response

        Returns:
            QuizResponse: Structured format for frontend
        """
        try:
            # Parse LLM response
            llm_data = self._parse_llm_response(llm_response)

            # Generate quiz metadata
            quiz_metadata = self._generate_quiz_metadata(quiz_config, context_chunks)

            # Transform questions
            questions = self._transform_questions(llm_data.get("questions", []), quiz_config)

            # Extract content summary
            content_summary = self._extract_content_summary(llm_data.get("content_analysis", {}))

            # Build scoring info
            scoring_info = self._build_scoring_info(quiz_config)

            # Create generation metadata
            generation_metadata = self._create_generation_metadata(
                query_metadata, context_chunks, generation_time_ms
            )

            # Assemble final response
            quiz_data = QuizData(
                quiz_metadata=quiz_metadata,
                questions=questions,
                content_summary=content_summary,
                scoring_info=scoring_info
            )

            return QuizResponse(
                quiz_data=quiz_data,
                generation_metadata=generation_metadata
            )

        except Exception as e:
            self.logger.error(f"Error transforming LLM response to frontend format: {str(e)}")
            raise

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """Parse and validate LLM JSON response."""
        try:
            # Remove any markdown formatting if present
            if "```json" in llm_response:
                start = llm_response.find("```json") + 7
                end = llm_response.find("```", start)
                if end != -1:
                    llm_response = llm_response[start:end].strip()
            elif "```" in llm_response:
                start = llm_response.find("```") + 3
                end = llm_response.find("```", start)
                if end != -1:
                    llm_response = llm_response[start:end].strip()

            return json.loads(llm_response)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON response: {str(e)}")
            return {"questions": [], "content_analysis": {}}

    def _generate_quiz_metadata(self, quiz_config: QuizConfig, context_chunks: List[ChunkConfig]) -> QuizMetadata:
        """Generate quiz metadata from quiz config and context."""
        quiz_id = str(uuid.uuid4())

        # Generate title based on collection and difficulty
        title = f"{quiz_config.collection_name.replace('_', ' ').title()} Quiz - {quiz_config.difficulty.title()}"

        # Create source info
        source = QuizSource(
            type="collection",
            collection_name=quiz_config.collection_name,
            source_count=len(context_chunks)
        )

        return QuizMetadata(
            quiz_id=quiz_id,
            title=title,
            difficulty=quiz_config.difficulty,
            estimated_time_minutes=quiz_config.time_limit_minutes,
            total_questions=quiz_config.num_questions,
            max_score=quiz_config.total_score,
            created_at=datetime.utcnow().isoformat() + "Z",
            source=source
        )

    def _transform_questions(self, llm_questions: List[Dict[str, Any]], quiz_config: QuizConfig) -> List[QuizQuestion]:
        """Transform LLM questions to frontend format with business logic."""
        transformed_questions = []

        for i, llm_question in enumerate(llm_questions[:quiz_config.num_questions]):
            # Extract topic from question text
            topic = self._extract_topic_from_question(llm_question.get("question_text", ""))

            # Generate question ID with topic prefix
            question_id = self._generate_question_id(topic, i + 1)

            # Build question config
            question_config = QuestionConfig(
                question_text=llm_question.get("question_text", ""),
                type="multiple_choice",  # Default from UI config
                difficulty=quiz_config.difficulty,
                topic=topic,
                requires_diagram=llm_question.get("requires_diagram", False),
                contains_math=llm_question.get("contains_math", False),
                diagram_type=llm_question.get("diagram_type")
            )

            # Transform options to A, B, C, D format
            answer_config = self._transform_answer_config(llm_question, quiz_config)

            # Build context
            context = QuestionContext(
                explanation=llm_question.get("explanation", ""),
                source_reference=self._generate_source_reference(topic),
                learning_objective=self._generate_learning_objective(topic, llm_question.get("question_text", ""))
            )

            transformed_question = QuizQuestion(
                question_id=question_id,
                question_config=question_config,
                answer_config=answer_config,
                context=context
            )

            transformed_questions.append(transformed_question)

        return transformed_questions

    def _extract_topic_from_question(self, question_text: str) -> str:
        """Extract physics topic from question text using keyword matching."""
        question_lower = question_text.lower()

        # Check for topic keywords
        for keyword, topic in self.PHYSICS_TOPICS.items():
            if keyword in question_lower:
                return topic

        # Default fallback
        return "Physics"

    def _generate_question_id(self, topic: str, question_num: int) -> str:
        """Generate question ID with topic prefix."""
        # Convert topic to lowercase and replace spaces with underscores
        topic_prefix = topic.lower().replace("'", "").replace(" ", "_")
        return f"{topic_prefix}_q{question_num}"

    def _transform_answer_config(self, llm_question: Dict[str, Any], quiz_config: QuizConfig) -> AnswerConfig:
        """Transform LLM answer format to frontend A,B,C,D format."""
        options = llm_question.get("options", [])
        correct_answer_text = llm_question.get("correct_answer", "")

        # Convert to A, B, C, D format
        option_labels = ["A", "B", "C", "D"]
        formatted_options = {}
        correct_label = "A"

        for i, option in enumerate(options[:4]):
            label = option_labels[i]
            formatted_options[label] = option

            # Find which label corresponds to the correct answer
            if option == correct_answer_text:
                correct_label = label

        return AnswerConfig(
            options=formatted_options,
            correct_answer=correct_label,
            max_score=quiz_config.points_per_question,
            partial_credit=False  # Default for multiple choice
        )

    def _generate_source_reference(self, topic: str) -> str:
        """Generate source reference based on topic."""
        return f"Chapter on {topic}"

    def _generate_learning_objective(self, topic: str, question_text: str) -> str:
        """Generate learning objective based on topic and question content."""
        if "calculate" in question_text.lower() or "find" in question_text.lower():
            return f"Apply {topic} concepts to solve problems"
        elif "explain" in question_text.lower() or "describe" in question_text.lower():
            return f"Understand and explain {topic} principles"
        else:
            return f"Demonstrate knowledge of {topic}"

    def _extract_content_summary(self, content_analysis: Dict[str, Any]) -> ContentSummary:
        """Extract content summary from LLM content analysis."""
        return ContentSummary(
            main_summary=content_analysis.get("main_summary", "Physics quiz covering fundamental concepts"),
            key_concepts=content_analysis.get("key_concepts", ["Physics concepts"]),
            topics_covered=content_analysis.get("topics_covered", ["Physics"]),
            prerequisite_knowledge=content_analysis.get("prerequisite_knowledge", ["Basic physics knowledge"])
        )

    def _build_scoring_info(self, quiz_config: QuizConfig) -> ScoringInfo:
        """Build scoring info from quiz config."""
        return ScoringInfo(
            total_score=quiz_config.total_score,
            passing_score=quiz_config.passing_score,
            time_limit_minutes=quiz_config.time_limit_minutes
        )

    def _create_generation_metadata(
        self,
        query_metadata: Dict[str, Any],
        context_chunks: List[ChunkConfig],
        generation_time_ms: int
    ) -> GenerationMetadata:
        """Create generation metadata from query data."""

        # Transform chunks to content sources
        content_sources = []
        for chunk in context_chunks[:3]:  # Limit to top 3 sources
            content_sources.append(ContentSource(
                source_id=chunk.source,
                content_preview=chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
                relevance_score=0.85  # Default score, could be enhanced with actual scores
            ))

        return GenerationMetadata(
            confidence=query_metadata.get("confidence", 0.85),
            is_relevant=query_metadata.get("is_relevant", True),
            generation_time_ms=generation_time_ms,
            model_used=query_metadata.get("model_used", "gemini"),
            content_sources=content_sources
        )