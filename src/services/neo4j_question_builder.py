"""
Neo4j Question Builder - Main Orchestrator
Unified service that coordinates Neo4j-driven question generation for UGC NET.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from models.question_models import (
    QuestionGenerationRequest, QuestionGenerationResponse, QuestionType,
    DifficultyLevel, QuestionRequest, GeneratedQuestion, QuestionMetadata,
    AssertionReasonQuestion, MatchFollowingQuestion
)
from services.assertion_reasoning_builder import assertion_reasoning_builder
from services.match_following_builder import match_following_builder
from services.question_formatter import question_formatter

logger = logging.getLogger(__name__)


class Neo4jQuestionBuilder:
    """
    Main orchestrator for Neo4j-driven question generation
    Coordinates builders, formatters, and validation
    """

    def __init__(self):
        self.ar_builder = assertion_reasoning_builder
        self.mf_builder = match_following_builder
        self.formatter = question_formatter
        self.generated_questions_cache = set()

    def build_questions(self, request: QuestionGenerationRequest) -> QuestionGenerationResponse:
        """
        Main entry point for question generation using Neo4j intelligence
        """
        try:
            logger.info(f"Starting Neo4j question generation for {len(request.questions)} question types")

            all_questions = []
            generation_stats = {
                'total_requested': sum(q.count for q in request.questions),
                'by_type': {},
                'by_difficulty': {},
                'neo4j_query_time': 0,
                'pattern_analysis_time': 0,
                'formatting_time': 0,
                'total_chunks_analyzed': 0
            }
            errors = []
            warnings = []

            # Process each question request
            for question_request in request.questions:
                try:
                    start_time = datetime.now()

                    # Build questions based on type
                    if question_request.type == QuestionType.ASSERTION_REASONING:
                        questions = self._build_assertion_reasoning_questions(question_request, request.context)
                    elif question_request.type == QuestionType.MATCH_FOLLOWING:
                        questions = self._build_match_following_questions(question_request, request.context)
                    else:
                        warnings.append(f"Unsupported question type: {question_request.type.value}")
                        continue

                    processing_time = (datetime.now() - start_time).total_seconds()

                    all_questions.extend(questions)

                    # Update statistics
                    gen_type = question_request.type.value
                    generation_stats['by_type'][gen_type] = (
                        generation_stats['by_type'].get(gen_type, 0) + len(questions)
                    )

                    for q in questions:
                        difficulty = q.metadata.difficulty.value
                        generation_stats['by_difficulty'][difficulty] = (
                            generation_stats['by_difficulty'].get(difficulty, 0) + 1
                        )

                    logger.info(f"Generated {len(questions)} {gen_type} questions in {processing_time:.2f}s")

                except Exception as e:
                    error_msg = f"Failed to generate {question_request.type.value} questions: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Final validation and response
            success = len(all_questions) > 0

            if len(all_questions) < generation_stats['total_requested']:
                warnings.append(
                    f"Generated {len(all_questions)} questions, "
                    f"requested {generation_stats['total_requested']}"
                )

            logger.info(
                f"Neo4j question generation completed: "
                f"success={success}, generated={len(all_questions)}, errors={len(errors)}"
            )

            return QuestionGenerationResponse(
                success=success,
                total_generated=len(all_questions),
                questions=all_questions,
                generation_stats=generation_stats,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Neo4j question generation failed: {e}")
            return QuestionGenerationResponse(
                success=False,
                total_generated=0,
                questions=[],
                errors=[f"Generation failed: {str(e)}"]
            )

    def _build_assertion_reasoning_questions(
        self,
        request: QuestionRequest,
        context
    ) -> List[GeneratedQuestion]:
        """Build assertion-reasoning questions using Neo4j intelligence"""

        questions = []

        try:
            # Step 1: Use Neo4j builder to get structured question data
            ar_data_list = self.ar_builder.build_questions(
                request.difficulty,
                request.count,
                request.filters
            )

            if not ar_data_list:
                logger.warning("No assertion-reasoning data generated from Neo4j")
                return questions

            # Step 2: Format each question using minimal LLM
            for ar_data in ar_data_list:
                try:
                    # Format question for human readability
                    formatted_question = self.formatter.format_assertion_reasoning(ar_data)

                    # Validate question quality
                    validation = self.formatter.validate_question_quality(formatted_question)

                    if validation['is_valid']:
                        # Create the final question object
                        question = self._create_assertion_reasoning_question_object(
                            formatted_question,
                            request.difficulty,
                            ar_data.source_chunks
                        )
                        questions.append(question)
                    else:
                        logger.warning(f"Question failed validation: {validation['issues']}")

                except Exception as e:
                    logger.error(f"Failed to format assertion-reasoning question: {e}")
                    continue

            logger.info(f"Successfully built {len(questions)} assertion-reasoning questions")

        except Exception as e:
            logger.error(f"Failed to build assertion-reasoning questions: {e}")

        return questions

    def _build_match_following_questions(
        self,
        request: QuestionRequest,
        context
    ) -> List[GeneratedQuestion]:
        """Build match-the-following questions using Neo4j intelligence"""

        questions = []

        try:
            # Step 1: Use Neo4j builder to get structured question data
            mf_data_list = self.mf_builder.build_questions(
                request.difficulty,
                request.count,
                request.filters
            )

            if not mf_data_list:
                logger.warning("No match-following data generated from Neo4j")
                return questions

            # Step 2: Format each question using minimal LLM
            for mf_data in mf_data_list:
                try:
                    # Format question for human readability
                    formatted_question = self.formatter.format_match_following(mf_data)

                    # Validate question quality
                    validation = self.formatter.validate_question_quality(formatted_question)

                    if validation['is_valid']:
                        # Create the final question object
                        question = self._create_match_following_question_object(
                            formatted_question,
                            request.difficulty,
                            mf_data.source_chunks
                        )
                        questions.append(question)
                    else:
                        logger.warning(f"Question failed validation: {validation['issues']}")

                except Exception as e:
                    logger.error(f"Failed to format match-following question: {e}")
                    continue

            logger.info(f"Successfully built {len(questions)} match-following questions")

        except Exception as e:
            logger.error(f"Failed to build match-following questions: {e}")

        return questions

    def _create_assertion_reasoning_question_object(
        self,
        formatted_question,
        difficulty: DifficultyLevel,
        source_chunks: List[str]
    ) -> GeneratedQuestion:
        """Create AssertionReasonQuestion object from formatted data"""

        question_content = AssertionReasonQuestion(
            question_text=formatted_question.question_text,
            assertion=formatted_question.content['assertion'],
            reason=formatted_question.content['reason'],
            options=formatted_question.content['options'],
            correct_option=formatted_question.content['correct_option'],
            explanation=formatted_question.content['explanation'],
            difficulty=difficulty,
            source_chunks=source_chunks
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.ASSERTION_REASONING,
            difficulty=difficulty,
            estimated_time=formatted_question.estimated_time,
            source_entities=[],
            source_files=list(set(self._extract_file_ids_from_chunks(source_chunks))),
            generated_at=datetime.now().isoformat(),
            quality_score=0.8  # Default quality score for Neo4j-generated questions
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _create_match_following_question_object(
        self,
        formatted_question,
        difficulty: DifficultyLevel,
        source_chunks: List[str]
    ) -> GeneratedQuestion:
        """Create MatchFollowingQuestion object from formatted data"""

        question_content = MatchFollowingQuestion(
            question_text=formatted_question.question_text,
            list_I=formatted_question.content['list_I'],
            list_II=formatted_question.content['list_II'],
            correct_matches=formatted_question.content['correct_matches'],
            explanation=formatted_question.content['explanation'],
            difficulty=difficulty,
            source_chunks=source_chunks
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.MATCH_FOLLOWING,
            difficulty=difficulty,
            estimated_time=formatted_question.estimated_time,
            source_entities=[],
            source_files=list(set(self._extract_file_ids_from_chunks(source_chunks))),
            generated_at=datetime.now().isoformat(),
            quality_score=0.8  # Default quality score for Neo4j-generated questions
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _extract_file_ids_from_chunks(self, source_chunks: List[str]) -> List[str]:
        """Extract file IDs from chunk IDs (if they follow a pattern)"""
        # This is a simple extraction - adjust based on your chunk ID format
        file_ids = []
        for chunk_id in source_chunks:
            # Assuming chunk_id format like "file_id_chunk_number"
            parts = chunk_id.split('_chunk_')
            if len(parts) > 1:
                file_id = parts[0]
                file_ids.append(file_id)

        return list(set(file_ids)) if file_ids else ["unknown"]

    def get_generation_capabilities(self) -> Dict[str, Any]:
        """Get information about generation capabilities"""
        return {
            "supported_question_types": [
                {
                    "type": "assertion_reasoning",
                    "name": "Assertion-Reasoning",
                    "description": "UGC NET format with standard 4 options",
                    "neo4j_driven": True,
                    "llm_formatting": "minimal"
                },
                {
                    "type": "match_following",
                    "name": "Match the Following",
                    "description": "4x4 matching with concept-definition pairs",
                    "neo4j_driven": True,
                    "llm_formatting": "minimal"
                }
            ],
            "difficulty_levels": ["easy", "moderate", "difficult"],
            "content_analysis": {
                "pattern_recognition": True,
                "legal_entity_extraction": True,
                "relationship_analysis": True,
                "complexity_scoring": True
            },
            "quality_assurance": {
                "neo4j_validation": True,
                "llm_formatting": True,
                "duplicate_prevention": True,
                "difficulty_verification": True
            },
            "performance": {
                "avg_generation_time_per_question": "2-5 seconds",
                "max_questions_per_request": 20,
                "reliability": "high (Neo4j-driven)"
            }
        }

    def analyze_content_suitability(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze if content is suitable for question generation"""
        try:
            from services.content_selector import content_selector

            # Get content statistics
            stats = content_selector.get_content_statistics()

            suitability = {
                "total_chunks": stats.get('total_chunks', 0),
                "suitable_for_ar": 0,
                "suitable_for_mf": 0,
                "content_quality": "unknown",
                "recommendations": []
            }

            total_chunks = suitability["total_chunks"]

            if total_chunks == 0:
                suitability["content_quality"] = "insufficient"
                suitability["recommendations"].append("No content chunks available for question generation")
                return suitability

            # Estimate suitability based on content volume
            if total_chunks >= 100:
                suitability["suitable_for_ar"] = min(total_chunks // 4, 50)  # Rough estimate
                suitability["suitable_for_mf"] = min(total_chunks // 8, 20)  # Need more chunks for variety
                suitability["content_quality"] = "good"
            elif total_chunks >= 50:
                suitability["suitable_for_ar"] = min(total_chunks // 6, 20)
                suitability["suitable_for_mf"] = min(total_chunks // 12, 10)
                suitability["content_quality"] = "moderate"
            else:
                suitability["suitable_for_ar"] = min(total_chunks // 10, 5)
                suitability["suitable_for_mf"] = min(total_chunks // 20, 2)
                suitability["content_quality"] = "limited"
                suitability["recommendations"].append("More content needed for better question variety")

            if suitability["suitable_for_ar"] < 5:
                suitability["recommendations"].append("Consider adding more content for assertion-reasoning questions")

            if suitability["suitable_for_mf"] < 3:
                suitability["recommendations"].append("Consider adding more content for match-following questions")

            return suitability

        except Exception as e:
            logger.error(f"Failed to analyze content suitability: {e}")
            return {
                "total_chunks": 0,
                "suitable_for_ar": 0,
                "suitable_for_mf": 0,
                "content_quality": "error",
                "recommendations": ["Failed to analyze content"]
            }


# Singleton instance
neo4j_question_builder = Neo4jQuestionBuilder()