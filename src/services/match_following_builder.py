"""
Match-the-Following Question Builder using Neo4j Intelligence
Generates UGC NET format match-the-following questions from graph data.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import random

from services.graph_service import graph_service
from services.content_pattern_analyzer import content_pattern_analyzer, ConceptDefinition
from models.question_models import DifficultyLevel, QuestionFilters

logger = logging.getLogger(__name__)


@dataclass
class MFQuestionData:
    """Structured match-the-following question data from Neo4j"""
    list_I: List[str]  # 4 items
    list_II: List[str]  # 4 items
    correct_matches: Dict[str, str]  # List I -> List II mapping
    explanation: str
    source_chunks: List[str]
    difficulty: DifficultyLevel
    confidence: float


class MatchFollowingBuilder:
    """
    Builds match-the-following questions using Neo4j graph intelligence
    """

    def __init__(self):
        self.pattern_analyzer = content_pattern_analyzer

    def build_questions(
        self,
        difficulty: DifficultyLevel,
        count: int,
        filters: Optional[QuestionFilters] = None
    ) -> List[MFQuestionData]:
        """Build match-the-following questions using Neo4j and pattern analysis"""

        try:
            logger.info(f"Building {count} match-the-following questions, difficulty: {difficulty.value}")

            # Step 1: Get relevant chunks from Neo4j
            chunks_data = self._get_relevant_chunks(difficulty, count * 8, filters)  # Need more chunks for variety

            if not chunks_data:
                logger.warning("No chunks found for match-following questions")
                return []

            logger.info(f"Found {len(chunks_data)} candidate chunks")

            # Step 2: Extract concept-definition pairs
            concept_definitions = self._extract_concept_definitions(chunks_data)

            if len(concept_definitions) < 4:
                logger.warning(f"Not enough concept definitions found: {len(concept_definitions)}")
                return []

            logger.info(f"Extracted {len(concept_definitions)} concept definitions")

            # Step 3: Build questions from concept pairs
            questions = self._build_questions_from_concepts(concept_definitions, difficulty, count)

            logger.info(f"Successfully built {len(questions)} match-following questions")
            return questions

        except Exception as e:
            logger.error(f"Failed to build match-following questions: {e}")
            return []

    def _get_relevant_chunks(
        self,
        difficulty: DifficultyLevel,
        limit: int,
        filters: Optional[QuestionFilters]
    ) -> List[Dict[str, Any]]:
        """Get chunks from Neo4j optimized for match-the-following questions"""

        # Base conditions
        base_conditions = ["c.chunk_type = 'concept'", "size(c.text) > 150"]

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
            # Look for clear definition language
            specific_conditions = """
            AND (c.text =~ '.*[Mm]eans.*' OR c.text =~ '.*[Rr]efers to.*' OR
                 c.text =~ '.*[Dd]efined as.*' OR c.text =~ '.*[Ii]s.*' OR
                 c.text =~ '.*[Aa]re.*')
            AND size(c.text) < 700
            """
            strategy = "easy_definition_patterns"

        elif difficulty == DifficultyLevel.MODERATE:
            # Look for legal entities and case references
            specific_conditions = """
            AND (c.text =~ '.*[Aa]rticle [0-9]+.*' OR c.text =~ '.*[Ss]ection [0-9]+.*' OR
                 c.text =~ '.*[Cc]ase.*' OR c.text =~ '.*[Jj]udgment.*' OR
                 c.text =~ '.*[Aa]ct.*' OR c.text =~ '.*[Cc]onstitution.*')
            AND size(c.text) BETWEEN 200 AND 1000
            """
            strategy = "moderate_legal_entity_patterns"

        else:  # DIFFICULT
            # Look for complex legal relationships
            specific_conditions = """
            AND (c.text =~ '.*[Pp]rinciple.*' OR c.text =~ '.*[Dd]octrine.*' OR
                 c.text =~ '.*[Jj]urisdiction.*' OR c.text =~ '.*[Pp]recedent.*' OR
                 c.text =~ '.*[Ii]nterpretation.*')
            AND size(c.text) > 300
            """
            strategy = "difficult_complex_legal_concepts"

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

    def _extract_concept_definitions(self, chunks_data: List[Dict[str, Any]]) -> List[ConceptDefinition]:
        """Extract concept-definition pairs from chunk data"""
        all_definitions = []

        for chunk_data in chunks_data:
            chunk_id = chunk_data['chunk_id']
            text = chunk_data['text']

            # Use pattern analyzer to extract concept definitions
            definitions = self.pattern_analyzer.extract_concept_definitions(text, chunk_id)
            all_definitions.extend(definitions)

        # Sort by confidence and return best definitions
        return sorted(all_definitions, key=lambda x: x.confidence, reverse=True)

    def _build_questions_from_concepts(
        self,
        definitions: List[ConceptDefinition],
        difficulty: DifficultyLevel,
        count: int
    ) -> List[MFQuestionData]:
        """Build complete match-the-following questions from concept definitions"""
        questions = []

        # Group definitions by concept type for better variety
        grouped_definitions = self._group_definitions_by_type(definitions)

        for question_num in range(count):
            try:
                # Select 4 diverse concept-definition pairs
                selected_pairs = self._select_diverse_pairs(grouped_definitions, 4)

                if len(selected_pairs) < 4:
                    logger.warning(f"Could not find 4 diverse pairs for question {question_num + 1}")
                    continue

                # Build the question structure
                question_data = self._create_question_from_pairs(selected_pairs, difficulty)

                if question_data:
                    questions.append(question_data)

                # Remove used definitions to avoid repetition
                for pair in selected_pairs:
                    self._remove_definition(grouped_definitions, pair)

            except Exception as e:
                logger.warning(f"Failed to build question {question_num + 1}: {e}")
                continue

        return questions

    def _group_definitions_by_type(self, definitions: List[ConceptDefinition]) -> Dict[str, List[ConceptDefinition]]:
        """Group definitions by concept type for better variety"""
        groups = {}

        for definition in definitions:
            concept_type = definition.concept_type
            if concept_type not in groups:
                groups[concept_type] = []
            groups[concept_type].append(definition)

        return groups

    def _select_diverse_pairs(
        self,
        grouped_definitions: Dict[str, List[ConceptDefinition]],
        count: int
    ) -> List[ConceptDefinition]:
        """Select diverse concept-definition pairs across different types"""
        selected_pairs = []

        # Try to get one from each type first
        available_types = [t for t, defs in grouped_definitions.items() if defs]

        # Select one from each available type up to count
        for concept_type in available_types[:count]:
            if grouped_definitions[concept_type]:
                # Take the highest confidence definition from this type
                best_definition = max(grouped_definitions[concept_type], key=lambda x: x.confidence)
                selected_pairs.append(best_definition)

        # If we need more pairs, take best remaining ones
        while len(selected_pairs) < count:
            remaining_definitions = []
            for definitions in grouped_definitions.values():
                for definition in definitions:
                    if definition not in selected_pairs:
                        remaining_definitions.append(definition)

            if not remaining_definitions:
                break

            # Take the best remaining definition
            best_remaining = max(remaining_definitions, key=lambda x: x.confidence)
            selected_pairs.append(best_remaining)

        return selected_pairs[:count]

    def _create_question_from_pairs(
        self,
        pairs: List[ConceptDefinition],
        difficulty: DifficultyLevel
    ) -> Optional[MFQuestionData]:
        """Create a complete match-the-following question from selected pairs"""

        if len(pairs) < 4:
            return None

        # Create List I (concepts) and List II (definitions)
        list_I = []
        list_II = []
        correct_matches = {}
        source_chunks = []

        for pair in pairs:
            # Clean and format concept and definition
            concept = self._format_concept(pair.concept)
            definition = self._format_definition(pair.definition)

            list_I.append(concept)
            list_II.append(definition)
            correct_matches[concept] = definition
            source_chunks.append(pair.source_chunk_id)

        # Shuffle List II to make it challenging (but keep track of correct matches)
        shuffled_list_II = list_II.copy()
        random.shuffle(shuffled_list_II)

        # Generate explanation
        explanation = self._generate_explanation(pairs, difficulty)

        # Calculate overall confidence
        avg_confidence = sum(pair.confidence for pair in pairs) / len(pairs)

        return MFQuestionData(
            list_I=list_I,
            list_II=shuffled_list_II,
            correct_matches=correct_matches,
            explanation=explanation,
            source_chunks=source_chunks,
            difficulty=difficulty,
            confidence=avg_confidence
        )

    def _format_concept(self, concept: str) -> str:
        """Format concept text for List I"""
        # Clean up the concept
        concept = concept.strip()

        # Capitalize properly if it's a legal term
        if concept.lower().startswith(('article', 'section')):
            words = concept.split()
            words[0] = words[0].capitalize()
            concept = ' '.join(words)

        # Handle case names (capitalize properly)
        if ' v ' in concept.lower() or ' vs ' in concept.lower():
            concept = self._format_case_name(concept)

        return concept

    def _format_definition(self, definition: str) -> str:
        """Format definition text for List II"""
        # Clean up the definition
        definition = definition.strip()

        # Ensure it starts with capital letter
        if definition and definition[0].islower():
            definition = definition[0].upper() + definition[1:]

        # Ensure it ends with period
        if definition and not definition.endswith('.'):
            definition += '.'

        # Remove redundant phrases
        redundant_phrases = ['means that', 'refers to the fact that', 'is defined as']
        for phrase in redundant_phrases:
            definition = definition.replace(phrase, '')

        return definition.strip()

    def _format_case_name(self, case_name: str) -> str:
        """Format case name properly"""
        # Split by 'v' or 'vs' and capitalize each part
        if ' v ' in case_name.lower():
            parts = case_name.split(' v ')
        else:
            parts = case_name.split(' vs ')

        formatted_parts = []
        for part in parts:
            formatted_parts.append(part.strip().title())

        return ' v. '.join(formatted_parts)

    def _generate_explanation(self, pairs: List[ConceptDefinition], difficulty: DifficultyLevel) -> str:
        """Generate explanation for the matches"""

        explanations = []

        for pair in pairs:
            concept_type = pair.concept_type

            if concept_type == 'constitutional':
                explanations.append(f"{pair.concept} is a constitutional provision")
            elif concept_type == 'case':
                explanations.append(f"{pair.concept} is a landmark legal case")
            elif concept_type == 'statute':
                explanations.append(f"{pair.concept} is statutory law")
            elif concept_type == 'legal_principle':
                explanations.append(f"{pair.concept} is a fundamental legal principle")
            else:
                explanations.append(f"{pair.concept} is a legal concept")

        # Create a comprehensive explanation
        base_explanation = "Each concept in List I corresponds to its definition or explanation in List II based on legal principles and constitutional provisions."

        if len(explanations) > 0:
            detailed_explanation = " ".join(explanations[:2])  # Limit to avoid long explanations
            return f"{base_explanation} {detailed_explanation}."

        return base_explanation

    def _remove_definition(self, grouped_definitions: Dict[str, List[ConceptDefinition]], definition: ConceptDefinition):
        """Remove a definition from the grouped definitions to avoid reuse"""
        concept_type = definition.concept_type
        if concept_type in grouped_definitions:
            if definition in grouped_definitions[concept_type]:
                grouped_definitions[concept_type].remove(definition)


# Singleton instance
match_following_builder = MatchFollowingBuilder()