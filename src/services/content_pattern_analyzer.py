"""
Content Pattern Analyzer for Neo4j-Driven Question Generation
Extracts legal patterns, concepts, and relationships from text using regex and NLP.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AssertionReasonPattern:
    """Extracted assertion-reason pattern from legal text"""
    assertion_text: str
    reason_text: str
    relationship_type: str  # 'supports', 'contradicts', 'explains', 'unrelated'
    confidence: float
    source_chunk_id: str


@dataclass
class ConceptDefinition:
    """Extracted concept-definition pair from legal text"""
    concept: str
    definition: str
    concept_type: str  # 'legal_term', 'case', 'article', 'statute'
    confidence: float
    source_chunk_id: str


@dataclass
class LegalEntity:
    """Extracted legal entity from text"""
    text: str
    entity_type: str  # 'case', 'article', 'statute', 'section', 'concept'
    context: str
    position: Tuple[int, int]  # start, end positions


class ContentPatternAnalyzer:
    """
    Analyzes legal content to extract patterns suitable for UGC NET questions
    """

    def __init__(self):
        # Assertion-Reason patterns
        self.assertion_patterns = {
            'causal': [
                r'(.+?)\s+because\s+(.+)',
                r'(.+?)\s+since\s+(.+)',
                r'(.+?)\s+as\s+(.+)',
                r'(.+?)\s+due to\s+(.+)'
            ],
            'conclusive': [
                r'(.+?)\s+therefore\s+(.+)',
                r'(.+?)\s+thus\s+(.+)',
                r'(.+?)\s+hence\s+(.+)',
                r'(.+?)\s+consequently\s+(.+)'
            ],
            'conditional': [
                r'if\s+(.+?),?\s+then\s+(.+)',
                r'when\s+(.+?),?\s+(.+)',
                r'provided that\s+(.+?),?\s+(.+)',
                r'in case\s+(.+?),?\s+(.+)'
            ],
            'contradictory': [
                r'(.+?)\s+however,?\s+(.+)',
                r'(.+?)\s+but\s+(.+)',
                r'(.+?)\s+nevertheless,?\s+(.+)',
                r'(.+?)\s+notwithstanding\s+(.+)',
                r'(.+?)\s+except\s+(.+)'
            ]
        }

        # Concept-Definition patterns
        self.definition_patterns = [
            r'(.+?)\s+means\s+(.+)',
            r'(.+?)\s+refers to\s+(.+)',
            r'(.+?)\s+is defined as\s+(.+)',
            r'(.+?)\s+shall mean\s+(.+)',
            r'the term\s+(.+?)\s+includes\s+(.+)',
            r'(.+?)\s+encompasses\s+(.+)',
            r'(.+?)\s+denotes\s+(.+)'
        ]

        # Legal Entity patterns
        self.legal_entity_patterns = {
            'case': [
                r'([A-Z][a-z]+\s+v\.?\s+[A-Z][a-zA-Z\s]+)',
                r'(.*?\s+case)',
                r'(.*?\s+judgment)'
            ],
            'article': [
                r'(Article\s+\d+[A-Z]?)',
                r'(Art\.?\s+\d+[A-Z]?)'
            ],
            'section': [
                r'(Section\s+\d+[A-Z]?)',
                r'(Sec\.?\s+\d+[A-Z]?)',
                r'(§\s*\d+[A-Z]?)'
            ],
            'statute': [
                r'([A-Z][a-zA-Z\s]+(Act|Code|Law)\s+\d{4})',
                r'(The\s+[A-Z][a-zA-Z\s]+Act)'
            ],
            'constitutional': [
                r'(Constitution of India)',
                r'(Constitutional\s+[A-Z][a-zA-Z\s]*)',
                r'(Fundamental\s+Rights?)',
                r'(Directive\s+Principles?)'
            ]
        }

        # Legal complexity indicators
        self.complexity_indicators = {
            'high': ['notwithstanding', 'provided that', 'subject to', 'in so far as', 'to the extent that'],
            'medium': ['however', 'although', 'except', 'unless', 'while', 'whereas'],
            'low': ['means', 'refers to', 'is', 'are', 'shall', 'will']
        }

    def extract_assertion_reason_patterns(self, text: str, chunk_id: str) -> List[AssertionReasonPattern]:
        """Extract assertion-reason patterns from legal text"""
        patterns = []

        for relationship_type, pattern_list in self.assertion_patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)

                for match in matches:
                    assertion_text = self._clean_text(match.group(1))
                    reason_text = self._clean_text(match.group(2))

                    # Skip if too short or too long
                    if not self._is_valid_text_length(assertion_text) or not self._is_valid_text_length(reason_text):
                        continue

                    confidence = self._calculate_pattern_confidence(assertion_text, reason_text, relationship_type)

                    if confidence > 0.5:  # Only keep high-confidence patterns
                        patterns.append(AssertionReasonPattern(
                            assertion_text=assertion_text,
                            reason_text=reason_text,
                            relationship_type=relationship_type,
                            confidence=confidence,
                            source_chunk_id=chunk_id
                        ))

        return sorted(patterns, key=lambda x: x.confidence, reverse=True)

    def extract_concept_definitions(self, text: str, chunk_id: str) -> List[ConceptDefinition]:
        """Extract concept-definition pairs from legal text"""
        definitions = []

        for pattern in self.definition_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                concept = self._clean_text(match.group(1))
                definition = self._clean_text(match.group(2))

                # Skip if invalid
                if not self._is_valid_concept(concept) or not self._is_valid_definition(definition):
                    continue

                concept_type = self._classify_concept_type(concept)
                confidence = self._calculate_definition_confidence(concept, definition)

                if confidence > 0.6:
                    definitions.append(ConceptDefinition(
                        concept=concept,
                        definition=definition,
                        concept_type=concept_type,
                        confidence=confidence,
                        source_chunk_id=chunk_id
                    ))

        return sorted(definitions, key=lambda x: x.confidence, reverse=True)

    def extract_legal_entities(self, text: str) -> List[LegalEntity]:
        """Extract legal entities from text"""
        entities = []

        for entity_type, pattern_list in self.legal_entity_patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    entity_text = match.group(1).strip()
                    start, end = match.span(1)

                    # Get context around the entity
                    context_start = max(0, start - 50)
                    context_end = min(len(text), end + 50)
                    context = text[context_start:context_end].strip()

                    entities.append(LegalEntity(
                        text=entity_text,
                        entity_type=entity_type,
                        context=context,
                        position=(start, end)
                    ))

        return entities

    def analyze_text_complexity(self, text: str) -> Dict[str, Any]:
        """Analyze the complexity of legal text for difficulty classification"""
        analysis = {
            'complexity_score': 0.0,
            'difficulty_level': 'easy',
            'indicators': {
                'high_complexity': [],
                'medium_complexity': [],
                'low_complexity': []
            },
            'metrics': {
                'avg_sentence_length': 0,
                'legal_term_density': 0,
                'clause_count': 0,
                'total_words': len(text.split())
            }
        }

        # Check complexity indicators
        text_lower = text.lower()
        for level, indicators in self.complexity_indicators.items():
            found_indicators = [ind for ind in indicators if ind in text_lower]
            analysis['indicators'][f'{level}_complexity'] = found_indicators

        # Calculate metrics
        sentences = re.split(r'[.!?]+', text)
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if valid_sentences:
            analysis['metrics']['avg_sentence_length'] = sum(len(s.split()) for s in valid_sentences) / len(valid_sentences)

        # Count clauses (rough approximation)
        analysis['metrics']['clause_count'] = len(re.findall(r'[,;:]', text)) + len(valid_sentences)

        # Legal term density (rough approximation)
        legal_terms = len(analysis['indicators']['high_complexity']) + len(analysis['indicators']['medium_complexity'])
        analysis['metrics']['legal_term_density'] = legal_terms / max(1, analysis['metrics']['total_words'] / 100)

        # Calculate overall complexity score
        complexity_score = self._calculate_complexity_score(analysis)
        analysis['complexity_score'] = complexity_score

        if complexity_score > 0.7:
            analysis['difficulty_level'] = 'difficult'
        elif complexity_score > 0.4:
            analysis['difficulty_level'] = 'moderate'
        else:
            analysis['difficulty_level'] = 'easy'

        return analysis

    def find_matching_concepts(self, chunks_data: List[Dict[str, Any]]) -> List[Tuple[str, str, float]]:
        """Find concept pairs suitable for match-the-following questions"""
        concept_pairs = []

        # Extract all concepts and definitions
        all_concepts = []
        for chunk_data in chunks_data:
            chunk_id = chunk_data['chunk_id']
            text = chunk_data['text']

            definitions = self.extract_concept_definitions(text, chunk_id)
            all_concepts.extend(definitions)

        # Group by concept type and create balanced pairs
        concept_groups = {}
        for concept in all_concepts:
            concept_type = concept.concept_type
            if concept_type not in concept_groups:
                concept_groups[concept_type] = []
            concept_groups[concept_type].append(concept)

        # Create pairs ensuring variety
        for concept_type, concepts in concept_groups.items():
            if len(concepts) >= 2:
                # Sort by confidence and take best ones
                concepts = sorted(concepts, key=lambda x: x.confidence, reverse=True)
                for i in range(0, min(4, len(concepts))):  # Max 4 per type
                    concept = concepts[i]
                    concept_pairs.append((concept.concept, concept.definition, concept.confidence))

        return sorted(concept_pairs, key=lambda x: x[2], reverse=True)

    # Helper methods
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove leading/trailing punctuation except periods
        text = re.sub(r'^[^\w]+|[^\w.]+$', '', text)

        return text

    def _is_valid_text_length(self, text: str) -> bool:
        """Check if text length is suitable for questions"""
        word_count = len(text.split())
        return 5 <= word_count <= 50  # Reasonable bounds for UGC NET

    def _is_valid_concept(self, concept: str) -> bool:
        """Validate concept for definition extraction"""
        word_count = len(concept.split())
        return 1 <= word_count <= 8 and not concept.lower().startswith(('the', 'a', 'an', 'this', 'that'))

    def _is_valid_definition(self, definition: str) -> bool:
        """Validate definition for concept extraction"""
        word_count = len(definition.split())
        return 3 <= word_count <= 30

    def _classify_concept_type(self, concept: str) -> str:
        """Classify the type of legal concept"""
        concept_lower = concept.lower()

        if any(pattern in concept_lower for pattern in ['article', 'section', 'amendment']):
            return 'constitutional'
        elif any(pattern in concept_lower for pattern in ['case', 'judgment', ' v ', ' vs ']):
            return 'case'
        elif any(pattern in concept_lower for pattern in ['act', 'law', 'code', 'statute']):
            return 'statute'
        elif any(pattern in concept_lower for pattern in ['right', 'principle', 'doctrine']):
            return 'legal_principle'
        else:
            return 'legal_term'

    def _calculate_pattern_confidence(self, assertion: str, reason: str, relationship_type: str) -> float:
        """Calculate confidence score for assertion-reason pattern"""
        score = 0.5  # Base score

        # Length appropriateness
        assertion_words = len(assertion.split())
        reason_words = len(reason.split())

        if 8 <= assertion_words <= 25:
            score += 0.2
        if 8 <= reason_words <= 25:
            score += 0.2

        # Legal content indicators
        legal_terms = ['court', 'constitutional', 'legal', 'statute', 'law', 'article', 'section']
        if any(term in assertion.lower() for term in legal_terms):
            score += 0.1
        if any(term in reason.lower() for term in legal_terms):
            score += 0.1

        return min(1.0, score)

    def _calculate_definition_confidence(self, concept: str, definition: str) -> float:
        """Calculate confidence score for concept-definition pair"""
        score = 0.6  # Base score

        # Concept clarity
        if concept.istitle() or concept.isupper():  # Proper noun or acronym
            score += 0.2

        # Definition completeness
        definition_words = len(definition.split())
        if 5 <= definition_words <= 20:
            score += 0.2

        return min(1.0, score)

    def _calculate_complexity_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall complexity score from analysis"""
        score = 0.0

        # Complexity indicators
        high_count = len(analysis['indicators']['high_complexity'])
        medium_count = len(analysis['indicators']['medium_complexity'])

        score += high_count * 0.3
        score += medium_count * 0.15

        # Sentence length
        avg_length = analysis['metrics']['avg_sentence_length']
        if avg_length > 25:
            score += 0.3
        elif avg_length > 15:
            score += 0.15

        # Legal term density
        density = analysis['metrics']['legal_term_density']
        score += min(0.2, density * 0.1)

        return min(1.0, score)


# Singleton instance
content_pattern_analyzer = ContentPatternAnalyzer()