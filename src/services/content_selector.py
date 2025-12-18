"""
Neo4j Graph-based Content Selector for Smart Question Generation
Leverages knowledge graph relationships to intelligently select content for different question types and difficulty levels.
"""

import logging
import random
from typing import List, Dict, Any, Optional, Tuple
from services.graph_service import graph_service
from models.question_models import (
    QuestionFilters, DifficultyLevel, QuestionType,
    ContentChunk, EntityRelationship, ContentSelectionResult
)

logger = logging.getLogger(__name__)


class ContentSelector:
    """
    Smart content selection using Neo4j knowledge graphs for UGC NET question generation
    """

    def __init__(self):
        self.entity_cache = {}
        self.relationship_cache = {}

    def select_content_for_question(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        filters: Optional[QuestionFilters] = None,
        count: int = 1
    ) -> ContentSelectionResult:
        """
        Select appropriate content chunks for question generation based on type and difficulty
        """
        try:
            if question_type == QuestionType.ASSERTION_REASONING:
                return self._select_for_assertion_reasoning(difficulty, filters, count)
            elif question_type == QuestionType.MATCH_FOLLOWING:
                return self._select_for_match_following(difficulty, filters, count)
            elif question_type == QuestionType.COMPREHENSION:
                return self._select_for_comprehension(difficulty, filters, count)
            else:
                raise ValueError(f"Unsupported question type: {question_type}")

        except Exception as e:
            logger.error(f"Content selection failed: {e}")
            return ContentSelectionResult(
                selected_chunks=[],
                selection_strategy=f"error_{question_type.value}",
                entity_relationships=[]
            )

    def _select_for_assertion_reasoning(
        self,
        difficulty: DifficultyLevel,
        filters: Optional[QuestionFilters],
        count: int
    ) -> ContentSelectionResult:
        """
        Select content for assertion-reasoning questions using contradictory/supportive relationships
        """
        # Build base query for chunks with contradictory language or relationships
        base_conditions = self._build_base_conditions(filters)

        if difficulty == DifficultyLevel.EASY:
            # Easy: Simple concept chunks with basic content
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 200
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 3, 15)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "easy_concept_chunks"

        elif difficulty == DifficultyLevel.MODERATE:
            # Moderate: Chunks with moderate length and complexity
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 300
            AND size(c.text) < 1200
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 3, 15)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "moderate_concept_chunks"

        else:  # DIFFICULT
            # Difficult: Longer, more complex chunks
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 500
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 2, 10)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "difficult_complex_chunks"

        # Execute query and process results
        params = self._build_query_params(filters)
        chunks = self._execute_and_process_chunks(query, params)
        relationships = self._find_related_entities(chunks, difficulty)

        return ContentSelectionResult(
            selected_chunks=chunks,
            entity_relationships=relationships,
            selection_strategy=strategy
        )

    def _select_for_match_following(
        self,
        difficulty: DifficultyLevel,
        filters: Optional[QuestionFilters],
        count: int
    ) -> ContentSelectionResult:
        """
        Select content for match-following questions using entity-definition relationships
        """
        base_conditions = self._build_base_conditions(filters)

        if difficulty == DifficultyLevel.EASY:
            # Easy: Simple concept chunks for matching
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 200
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 8, 24)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "easy_concept_matching"

        elif difficulty == DifficultyLevel.MODERATE:
            # Moderate: Medium-length chunks for matching
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 300
            AND size(c.text) < 1000
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 6, 18)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "moderate_concept_matching"

        else:  # DIFFICULT
            # Difficult: Longer chunks for complex matching
            query = f"""
            MATCH (c:Chunk)
            WHERE {base_conditions}
            AND c.chunk_type = 'concept'
            AND size(c.text) > 500
            WITH c
            ORDER BY rand()
            LIMIT {min(count * 4, 12)}
            RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
                   coalesce(c.key_terms, []) as key_terms,
                   coalesce(c.chapter_title, '') as chapter_title,
                   coalesce(c.section_title, '') as section_title
            """
            strategy = "difficult_concept_matching"

        params = self._build_query_params(filters)
        chunks = self._execute_and_process_chunks(query, params)
        relationships = self._find_entity_definition_pairs(chunks, difficulty)

        return ContentSelectionResult(
            selected_chunks=chunks,
            entity_relationships=relationships,
            selection_strategy=strategy
        )

    def _select_for_comprehension(
        self,
        difficulty: DifficultyLevel,
        filters: Optional[QuestionFilters],
        count: int
    ) -> ContentSelectionResult:
        """
        Select content for comprehension questions using longer, coherent passages
        """
        base_conditions = self._build_base_conditions(filters)

        if difficulty == DifficultyLevel.EASY:
            # Easy: Clear, well-structured passages
            min_length = 800
            max_length = 1500
            strategy = "easy_structured_passages"

        elif difficulty == DifficultyLevel.MODERATE:
            # Moderate: Passages with some complexity
            min_length = 1200
            max_length = 2000
            strategy = "moderate_complex_passages"

        else:  # DIFFICULT
            # Difficult: Complex, dense legal texts
            min_length = 1500
            max_length = 3000
            strategy = "difficult_dense_legal_texts"

        query = f"""
        MATCH (c:Chunk)
        WHERE {base_conditions}
        AND size(c.text) >= {min_length}
        AND size(c.text) <= {max_length}
        AND c.chunk_type IN ['concept', 'example']
        WITH c, size(split(c.text, '.')) as sentence_count
        WHERE sentence_count >= 4
        ORDER BY rand()
        LIMIT {min(count * 2, 6)}
        RETURN c.chunk_id, c.text, c.file_id, c.collection_id, c.chunk_type,
               c.key_terms, c.chapter_title, c.section_title, sentence_count
        """

        params = self._build_query_params(filters)
        chunks = self._execute_and_process_chunks(query, params)
        relationships = self._find_passage_entities(chunks)

        return ContentSelectionResult(
            selected_chunks=chunks,
            entity_relationships=relationships,
            selection_strategy=strategy
        )

    def _build_base_conditions(self, filters: Optional[QuestionFilters]) -> str:
        """Build base WHERE conditions for content selection queries"""
        conditions = ["c.chunk_id IS NOT NULL"]

        if filters:
            if filters.collection_ids:
                conditions.append("c.collection_id IN $collection_ids")
            if filters.file_ids:
                conditions.append("c.file_id IN $file_ids")
            if filters.exclude_file_ids:
                conditions.append("c.file_id NOT IN $exclude_file_ids")
            if filters.chunk_types:
                conditions.append("c.chunk_type IN $chunk_types")
            if filters.chapters:
                conditions.append("c.chapter_title IN $chapters")
            if filters.min_text_length:
                conditions.append(f"size(c.text) >= {filters.min_text_length}")

        return " AND ".join(conditions)

    def _build_query_params(self, filters: Optional[QuestionFilters]) -> Dict[str, Any]:
        """Build query parameters from filters"""
        params = {}

        if filters:
            if filters.collection_ids:
                params['collection_ids'] = filters.collection_ids
            if filters.file_ids:
                params['file_ids'] = filters.file_ids
            if filters.exclude_file_ids:
                params['exclude_file_ids'] = filters.exclude_file_ids
            if filters.chunk_types:
                params['chunk_types'] = filters.chunk_types
            if filters.chapters:
                params['chapters'] = filters.chapters

        return params

    def _execute_and_process_chunks(self, query: str, params: Dict[str, Any]) -> List[ContentChunk]:
        """Execute Neo4j query and convert results to ContentChunk objects"""
        try:
            records = graph_service.execute_query(query, params)
            chunks = []

            for record in records:
                chunk = ContentChunk(
                    chunk_id=record.get('c.chunk_id') or record.get('chunk_id'),
                    text=(record.get('c.text') or record.get('text', ''))[:2000],  # Limit text length
                    file_id=record.get('c.file_id') or record.get('file_id'),
                    collection_id=record.get('c.collection_id') or record.get('collection_id'),
                    chunk_type=record.get('c.chunk_type') or record.get('chunk_type', 'concept'),
                    key_terms=record.get('c.key_terms') or record.get('key_terms', []),
                    chapter_title=record.get('c.chapter_title') or record.get('chapter_title', ''),
                    section_title=record.get('c.section_title') or record.get('section_title', ''),
                    entities=record.get('entities', [])
                )
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Failed to execute content selection query: {e}")
            return []

    def _find_related_entities(self, chunks: List[ContentChunk], difficulty: DifficultyLevel) -> List[EntityRelationship]:
        """Find entity relationships relevant for assertion-reasoning questions"""
        if not chunks:
            return []

        chunk_ids = [chunk.chunk_id for chunk in chunks]

        # Query for entity relationships
        query = """
        MATCH (c:Chunk)-[:MENTIONS]->(e1:LegalEntity)
        MATCH (e1)-[r]->(e2:LegalEntity)
        WHERE c.chunk_id IN $chunk_ids
        AND type(r) IN ['CONTRADICTS', 'SUPPORTS', 'DEFINES', 'HAS_EXCEPTION']
        RETURN e1.text as source, type(r) as relationship, e2.text as target,
               c.text as context
        LIMIT 10
        """

        try:
            records = graph_service.execute_query(query, {'chunk_ids': chunk_ids})
            relationships = []

            for record in records:
                rel = EntityRelationship(
                    source_entity=record['source'],
                    target_entity=record['target'],
                    relationship_type=record['relationship'],
                    context=record['context'][:200]
                )
                relationships.append(rel)

            return relationships

        except Exception as e:
            logger.error(f"Failed to find entity relationships: {e}")
            return []

    def _find_entity_definition_pairs(self, chunks: List[ContentChunk], difficulty: DifficultyLevel) -> List[EntityRelationship]:
        """Find entity-definition pairs for match-following questions"""
        if not chunks:
            return []

        chunk_ids = [chunk.chunk_id for chunk in chunks]

        query = """
        MATCH (c:Chunk)-[:MENTIONS]->(e:LegalEntity)
        WHERE c.chunk_id IN $chunk_ids
        AND (c.text CONTAINS 'define' OR c.text CONTAINS 'mean' OR c.text CONTAINS 'refer')
        RETURN e.text as entity, c.text as definition
        LIMIT 8
        """

        try:
            records = graph_service.execute_query(query, {'chunk_ids': chunk_ids})
            relationships = []

            for record in records:
                rel = EntityRelationship(
                    source_entity=record['entity'],
                    target_entity="definition",
                    relationship_type="DEFINES",
                    context=record['definition'][:300]
                )
                relationships.append(rel)

            return relationships

        except Exception as e:
            logger.error(f"Failed to find entity definition pairs: {e}")
            return []

    def _find_passage_entities(self, chunks: List[ContentChunk]) -> List[EntityRelationship]:
        """Find key entities mentioned in comprehension passages"""
        if not chunks:
            return []

        chunk_ids = [chunk.chunk_id for chunk in chunks]

        query = """
        MATCH (c:Chunk)-[:MENTIONS]->(e:LegalEntity)
        WHERE c.chunk_id IN $chunk_ids
        RETURN c.chunk_id as chunk, collect(e.text) as entities
        """

        try:
            records = graph_service.execute_query(query, {'chunk_ids': chunk_ids})
            relationships = []

            for record in records:
                for entity in record.get('entities', []):
                    rel = EntityRelationship(
                        source_entity=record['chunk'],
                        target_entity=entity,
                        relationship_type="MENTIONS",
                        context=""
                    )
                    relationships.append(rel)

            return relationships

        except Exception as e:
            logger.error(f"Failed to find passage entities: {e}")
            return []

    def get_content_statistics(self, filters: Optional[QuestionFilters] = None) -> Dict[str, Any]:
        """Get statistics about available content for question generation"""
        base_conditions = self._build_base_conditions(filters)

        query = f"""
        MATCH (c:Chunk)
        WHERE {base_conditions}
        RETURN
            count(c) as total_chunks,
            count(DISTINCT c.file_id) as unique_files,
            count(DISTINCT c.collection_id) as unique_collections,
            avg(size(c.text)) as avg_text_length,
            collect(DISTINCT c.chunk_type) as chunk_types,
            collect(DISTINCT c.chapter_title)[..10] as sample_chapters
        """

        try:
            params = self._build_query_params(filters)
            records = graph_service.execute_query(query, params)

            if records:
                return dict(records[0])
            return {}

        except Exception as e:
            logger.error(f"Failed to get content statistics: {e}")
            return {}


# Singleton instance
content_selector = ContentSelector()