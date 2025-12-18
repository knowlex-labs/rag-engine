"""
Assertion-Reasoning Question Builder using Neo4j Intelligence
Generates UGC NET format assertion-reasoning questions from graph data.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from services.graph_service import graph_service
from services.content_pattern_analyzer import content_pattern_analyzer, AssertionReasonPattern
from models.question_models import DifficultyLevel, QuestionFilters

logger = logging.getLogger(__name__)


@dataclass
class ARQuestionData:
    """Structured assertion-reasoning question data from Neo4j"""
    assertion: str
    reason: str
    correct_option: str
    explanation: str
    source_chunks: List[str]
    difficulty: DifficultyLevel
    confidence: float


class AssertionReasoningBuilder:
    """
    Builds assertion-reasoning questions using Neo4j graph intelligence
    """

    # Standard UGC NET Assertion-Reasoning options (always the same)
    STANDARD_OPTIONS = [
        "Both A and R are true and R is the correct explanation of A.",
        "Both A and R are true but R is not the correct explanation of A.",
        "A is true but R is false.",
        "A is false but R is true."
    ]

    def __init__(self):
        self.pattern_analyzer = content_pattern_analyzer

    def build_questions(
        self,
        difficulty: DifficultyLevel,
        count: int,
        filters: Optional[QuestionFilters] = None
    ) -> List[ARQuestionData]:
        """Build assertion-reasoning questions using Neo4j and pattern analysis"""

        try:
            logger.info(f"Building {count} assertion-reasoning questions, difficulty: {difficulty.value}")

            # Step 1: Get relevant chunks from Neo4j
            chunks_data = self._get_relevant_chunks(difficulty, count * 3, filters)  # Get extra for selection

            if not chunks_data:
                logger.warning("No chunks found for assertion-reasoning questions")
                return []

            logger.info(f"Found {len(chunks_data)} candidate chunks")

            # Step 2: Analyze chunks for assertion-reason patterns
            ar_patterns = self._extract_ar_patterns(chunks_data)

            if not ar_patterns:
                logger.warning("No assertion-reason patterns found")
                return []

            logger.info(f"Extracted {len(ar_patterns)} assertion-reason patterns")

            # Step 3: Build questions from patterns
            questions = self._build_questions_from_patterns(ar_patterns, difficulty, count)

            logger.info(f"Successfully built {len(questions)} assertion-reasoning questions")
            return questions

        except Exception as e:
            logger.error(f"Failed to build assertion-reasoning questions: {e}")
            return []

    def _get_relevant_chunks(
        self,
        difficulty: DifficultyLevel,
        limit: int,
        filters: Optional[QuestionFilters]
    ) -> List[Dict[str, Any]]:
        """Get chunks from Neo4j optimized for assertion-reasoning questions"""

        # Base conditions
        base_conditions = ["c.chunk_type = 'concept'", "size(c.text) > 200"]

        if filters:
            if filters.file_ids:
                base_conditions.append("c.file_id IN $file_ids")
            if filters.collection_ids:
                base_conditions.append("c.collection_id IN $collection_ids")
            if filters.exclude_file_ids:
                base_conditions.append("c.file_id NOT IN $exclude_file_ids")

        base_condition_str = " AND ".join(base_conditions)

        # Difficulty-specific patterns for better content selection
        if difficulty == DifficultyLevel.EASY:
            # Look for clear causal language
            specific_conditions = """
            AND (c.text =~ '.*[Bb]ecause.*' OR c.text =~ '.*[Ss]ince.*' OR
                 c.text =~ '.*[Tt]herefore.*' OR c.text =~ '.*[Tt]hus.*')
            AND size(c.text) < 800
            """
            strategy = "easy_causal_patterns"

        elif difficulty == DifficultyLevel.MODERATE:
            # Look for conditional or contrasting language
            specific_conditions = """
            AND (c.text =~ '.*[Hh]owever.*' OR c.text =~ '.*[Bb]ut.*' OR
                 c.text =~ '.*[Aa]lthough.*' OR c.text =~ '.*[Ww]hile.*' OR
                 c.text =~ '.*if.*then.*' OR c.text =~ '.*[Ww]hen.*')
            AND size(c.text) BETWEEN 300 AND 1200
            """
            strategy = "moderate_conditional_patterns"

        else:  # DIFFICULT
            # Look for complex legal language
            specific_conditions = """
            AND (c.text =~ '.*[Nn]otwithstanding.*' OR c.text =~ '.*[Pp]rovided that.*' OR
                 c.text =~ '.*[Ss]ubject to.*' OR c.text =~ '.*[Ii]n so far as.*' OR
                 c.text =~ '.*[Ee]xcept.*' OR c.text =~ '.*[Uu]nless.*')
            AND size(c.text) > 400
            """
            strategy = "difficult_complex_patterns"

        # Build final query
        query = f"""
        MATCH (c:Chunk)
        WHERE {base_condition_str}
        {specific_conditions}
        WITH c, rand() as r
        ORDER BY r
        LIMIT {limit}
        RETURN c.chunk_id, c.text, c.file_id, c.collection_id,
               coalesce(c.key_terms, []) as key_terms,
               coalesce(c.chapter_title, '') as chapter_title,
               coalesce(c.section_title, '') as section_title
        """

        # Build parameters
        params = {}
        if filters:
            if filters.file_ids:
                params['file_ids'] = filters.file_ids
            if filters.collection_ids:
                params['collection_ids'] = filters.collection_ids
            if filters.exclude_file_ids:
                params['exclude_file_ids'] = filters.exclude_file_ids

        try:
            records = graph_service.execute_query(query, params)
            chunks_data = []

            for record in records:
                chunks_data.append({
                    'chunk_id': record['chunk_id'],
                    'text': record['text'],
                    'file_id': record['file_id'],
                    'collection_id': record['collection_id'],
                    'key_terms': record.get('key_terms', []),
                    'chapter_title': record.get('chapter_title', ''),
                    'section_title': record.get('section_title', ''),
                    'selection_strategy': strategy
                })

            return chunks_data

        except Exception as e:
            logger.error(f"Failed to get chunks from Neo4j: {e}")
            return []

    def _extract_ar_patterns(self, chunks_data: List[Dict[str, Any]]) -> List[AssertionReasonPattern]:
        """Extract assertion-reason patterns from chunk data"""
        all_patterns = []

        for chunk_data in chunks_data:
            chunk_id = chunk_data['chunk_id']
            text = chunk_data['text']

            # Use pattern analyzer to extract AR patterns
            patterns = self.pattern_analyzer.extract_assertion_reason_patterns(text, chunk_id)
            all_patterns.extend(patterns)

        # Sort by confidence and return best patterns
        return sorted(all_patterns, key=lambda x: x.confidence, reverse=True)

    def _build_questions_from_patterns(
        self,
        patterns: List[AssertionReasonPattern],
        difficulty: DifficultyLevel,
        count: int
    ) -> List[ARQuestionData]:
        """Build complete questions from extracted patterns"""
        questions = []

        # Take the best patterns up to the requested count
        selected_patterns = patterns[:count * 2]  # Get more than needed for variety

        for pattern in selected_patterns:
            if len(questions) >= count:
                break

            try:
                # Determine the correct option based on pattern analysis
                correct_option, explanation = self._determine_correct_option(pattern)

                # Create question data
                question_data = ARQuestionData(
                    assertion=self._format_assertion(pattern.assertion_text),
                    reason=self._format_reason(pattern.reason_text),
                    correct_option=correct_option,
                    explanation=explanation,
                    source_chunks=[pattern.source_chunk_id],
                    difficulty=difficulty,
                    confidence=pattern.confidence
                )

                questions.append(question_data)

            except Exception as e:
                logger.warning(f"Failed to build question from pattern: {e}")
                continue

        return questions

    def _determine_correct_option(self, pattern: AssertionReasonPattern) -> Tuple[str, str]:
        """Determine the correct option based on pattern analysis"""

        relationship = pattern.relationship_type
        assertion = pattern.assertion_text.lower()
        reason = pattern.reason_text.lower()

        # Analyze the logical relationship
        if relationship in ['causal', 'conclusive']:
            # Check if reason actually explains assertion
            if self._is_correct_explanation(assertion, reason):
                correct_option = self.STANDARD_OPTIONS[0]  # Both true, R explains A
                explanation = f"The reason correctly explains the assertion through a {relationship} relationship."
            else:
                correct_option = self.STANDARD_OPTIONS[1]  # Both true, R doesn't explain A
                explanation = "Both statements are true but the reason doesn't directly explain the assertion."

        elif relationship == 'contradictory':
            # In contradictory cases, typically one is false
            if self._assertion_is_stronger(assertion, reason):
                correct_option = self.STANDARD_OPTIONS[2]  # A true, R false
                explanation = "The assertion is true but the reason contradicts it and is therefore false."
            else:
                correct_option = self.STANDARD_OPTIONS[3]  # A false, R true
                explanation = "The assertion is contradicted by the reason, making it false while the reason remains true."

        elif relationship == 'conditional':
            # Conditional relationships are usually both true but not explanatory
            correct_option = self.STANDARD_OPTIONS[1]  # Both true, R doesn't explain A
            explanation = "Both statements are true but represent a conditional relationship rather than direct explanation."

        else:
            # Default case - assume both true but not explanatory
            correct_option = self.STANDARD_OPTIONS[1]
            explanation = "Both statements are factually correct but the reason doesn't provide a direct explanation of the assertion."

        return correct_option, explanation

    def _is_correct_explanation(self, assertion: str, reason: str) -> bool:
        """Determine if reason correctly explains assertion"""

        # Look for explanatory keywords in reason
        explanatory_keywords = ['because', 'since', 'as', 'due to', 'owing to', 'caused by']

        # Look for shared legal concepts
        shared_concepts = self._find_shared_concepts(assertion, reason)

        # Simple heuristics for explanation detection
        has_explanatory_language = any(keyword in reason for keyword in explanatory_keywords)
        has_shared_concepts = len(shared_concepts) > 0

        # If reason has explanatory language and shares concepts, likely correct explanation
        return has_explanatory_language and has_shared_concepts

    def _assertion_is_stronger(self, assertion: str, reason: str) -> bool:
        """Determine which statement is stronger/more authoritative"""

        # Look for authoritative language in assertion
        authoritative_terms = ['constitution', 'supreme court', 'established', 'fundamental', 'statutory']

        assertion_score = sum(1 for term in authoritative_terms if term in assertion)
        reason_score = sum(1 for term in authoritative_terms if term in reason)

        return assertion_score >= reason_score

    def _find_shared_concepts(self, text1: str, text2: str) -> List[str]:
        """Find shared legal concepts between two texts"""

        legal_terms = ['court', 'constitution', 'law', 'legal', 'judicial', 'legislative', 'executive',
                      'fundamental', 'right', 'article', 'section', 'act', 'statute', 'provision']

        shared = []
        for term in legal_terms:
            if term in text1 and term in text2:
                shared.append(term)

        return shared

    def _format_assertion(self, assertion_text: str) -> str:
        """Format assertion text for UGC NET style"""
        # Clean up and ensure proper format
        assertion = assertion_text.strip()

        # Ensure it doesn't start with lowercase (unless intentional)
        if assertion and assertion[0].islower():
            assertion = assertion[0].upper() + assertion[1:]

        # Ensure proper ending punctuation
        if not assertion.endswith('.'):
            assertion += '.'

        return assertion

    def _format_reason(self, reason_text: str) -> str:
        """Format reason text for UGC NET style"""
        # Clean up and ensure proper format
        reason = reason_text.strip()

        # Ensure it doesn't start with lowercase
        if reason and reason[0].islower():
            reason = reason[0].upper() + reason[1:]

        # Ensure proper ending punctuation
        if not reason.endswith('.'):
            reason += '.'

        return reason


# Singleton instance
assertion_reasoning_builder = AssertionReasoningBuilder()