"""
Difficulty Analyzer Utility for UGC NET Question Generation
Analyzes content complexity to ensure questions match intended difficulty levels.
"""

import re
import math
import logging
from typing import Dict, List, Any, Optional
from collections import Counter
from models.question_models import DifficultyLevel, ContentChunk

logger = logging.getLogger(__name__)


class DifficultyAnalyzer:
    """
    Analyzes content complexity and validates question difficulty for UGC NET exam preparation
    """

    def __init__(self):
        # Complex legal terms that indicate higher difficulty
        self.complex_legal_terms = {
            'ultra_vires', 'stare_decisis', 'ratio_decidendi', 'obiter_dicta',
            'mandamus', 'certiorari', 'prohibition', 'quo_warranto',
            'fundamental_rights', 'directive_principles', 'constitutional_amendment',
            'judicial_review', 'separation_of_powers', 'federalism',
            'substantive_due_process', 'procedural_due_process', 'equal_protection',
            'interstate_commerce', 'enumerated_powers', 'implied_powers'
        }

        # Transitional phrases indicating complexity
        self.complexity_indicators = {
            'easy': ['means', 'refers to', 'define', 'is', 'are', 'simple'],
            'moderate': ['however', 'although', 'while', 'but', 'except', 'unless'],
            'difficult': ['notwithstanding', 'provided that', 'subject to',
                         'in so far as', 'to the extent that', 'except in cases where']
        }

        # Legal reasoning patterns
        self.reasoning_patterns = {
            'causal': ['because', 'since', 'as a result', 'therefore', 'thus', 'hence'],
            'conditional': ['if', 'when', 'unless', 'provided that', 'in case'],
            'comparative': ['unlike', 'similar to', 'compared to', 'in contrast'],
            'exception': ['except', 'however', 'but', 'nevertheless', 'notwithstanding']
        }

    def analyze_content_difficulty(self, chunk: ContentChunk) -> Dict[str, Any]:
        """
        Analyze a content chunk and return difficulty metrics
        """
        text = chunk.text.lower()

        metrics = {
            'readability_score': self._calculate_readability(chunk.text),
            'legal_complexity': self._analyze_legal_complexity(text),
            'sentence_complexity': self._analyze_sentence_complexity(chunk.text),
            'concept_density': self._calculate_concept_density(chunk),
            'reasoning_complexity': self._analyze_reasoning_patterns(text),
            'vocabulary_complexity': self._analyze_vocabulary_complexity(text),
            'overall_difficulty': DifficultyLevel.EASY
        }

        # Calculate overall difficulty
        metrics['overall_difficulty'] = self._calculate_overall_difficulty(metrics)

        return metrics

    def validate_question_difficulty(
        self,
        generated_question: Dict[str, Any],
        target_difficulty: DifficultyLevel,
        source_chunks: List[ContentChunk]
    ) -> Dict[str, Any]:
        """
        Validate if a generated question matches the target difficulty level
        """
        # Analyze question text complexity
        question_text = self._extract_question_text(generated_question)
        question_metrics = self._analyze_question_complexity(question_text)

        # Analyze source content difficulty
        source_difficulties = []
        for chunk in source_chunks:
            chunk_analysis = self.analyze_content_difficulty(chunk)
            source_difficulties.append(chunk_analysis)

        avg_source_difficulty = self._average_difficulty_score(source_difficulties)

        # Check alignment
        alignment_score = self._calculate_alignment_score(
            question_metrics, avg_source_difficulty, target_difficulty
        )

        return {
            'is_valid': alignment_score >= 0.7,
            'alignment_score': alignment_score,
            'question_difficulty': question_metrics['overall_difficulty'],
            'source_difficulty': avg_source_difficulty,
            'target_difficulty': target_difficulty,
            'recommendations': self._generate_recommendations(
                question_metrics, target_difficulty, alignment_score
            )
        }

    def _calculate_readability(self, text: str) -> float:
        """
        Calculate Flesch-Kincaid readability score adapted for legal text
        """
        sentences = len(re.findall(r'[.!?]+', text))
        words = len(text.split())
        syllables = self._count_syllables(text)

        if sentences == 0 or words == 0:
            return 0.0

        # Modified Flesch-Kincaid for legal complexity
        score = (
            206.835
            - (1.015 * (words / sentences))
            - (84.6 * (syllables / words))
        )

        # Normalize to 0-1 scale (higher = more readable = easier)
        return max(0, min(1, score / 100))

    def _count_syllables(self, text: str) -> int:
        """
        Estimate syllable count in text
        """
        # Simple syllable counting heuristic
        words = re.findall(r'\b\w+\b', text.lower())
        syllable_count = 0

        for word in words:
            vowels = re.findall(r'[aeiouy]', word)
            if len(vowels) == 0:
                syllable_count += 1
            else:
                syllable_count += len(vowels)
                # Adjust for silent e
                if word.endswith('e'):
                    syllable_count -= 1
                # Minimum 1 syllable per word
                if syllable_count == 0:
                    syllable_count = 1

        return syllable_count

    def _analyze_legal_complexity(self, text: str) -> float:
        """
        Analyze legal complexity based on specialized terminology
        """
        words = text.split()
        if not words:
            return 0.0

        complex_term_count = 0
        legal_term_count = 0

        for word in words:
            word_clean = re.sub(r'[^\w]', '', word.lower())

            # Check for complex legal terms
            if word_clean in self.complex_legal_terms:
                complex_term_count += 1

            # Check for general legal indicators
            if any(indicator in word_clean for indicator in
                   ['constitu', 'judici', 'legislat', 'statute', 'court', 'legal', 'law']):
                legal_term_count += 1

        # Calculate complexity ratio
        complexity_ratio = complex_term_count / len(words)
        legal_ratio = legal_term_count / len(words)

        return min(1.0, (complexity_ratio * 2 + legal_ratio) / 3)

    def _analyze_sentence_complexity(self, text: str) -> float:
        """
        Analyze sentence structure complexity
        """
        sentences = re.split(r'[.!?]+', text)
        if not sentences:
            return 0.0

        total_complexity = 0
        valid_sentences = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue

            valid_sentences += 1
            words = sentence.split()

            # Factors for complexity
            word_count = len(words)
            clause_count = len(re.findall(r'[,;:]', sentence)) + 1
            subordinate_clauses = len(re.findall(
                r'\b(that|which|who|whom|whose|where|when|while|although|because|since|if|unless)\b',
                sentence.lower()
            ))

            # Calculate sentence complexity score
            sentence_complexity = (
                (word_count / 20) * 0.4 +  # Word count factor
                (clause_count / 3) * 0.3 +  # Clause factor
                (subordinate_clauses / 2) * 0.3  # Subordination factor
            )

            total_complexity += min(1.0, sentence_complexity)

        return total_complexity / max(1, valid_sentences)

    def _calculate_concept_density(self, chunk: ContentChunk) -> float:
        """
        Calculate density of legal concepts in the chunk
        """
        text_length = len(chunk.text.split())
        if text_length == 0:
            return 0.0

        # Key terms density
        key_terms_density = len(chunk.key_terms) / text_length

        # Entity density (if available)
        entity_density = 0
        if hasattr(chunk, 'entities') and chunk.entities:
            entity_density = len(chunk.entities) / text_length

        # Combined density
        return min(1.0, (key_terms_density + entity_density) * 100)

    def _analyze_reasoning_patterns(self, text: str) -> float:
        """
        Analyze complexity of reasoning patterns in text
        """
        pattern_counts = {}

        for pattern_type, patterns in self.reasoning_patterns.items():
            count = sum(len(re.findall(rf'\b{pattern}\b', text)) for pattern in patterns)
            pattern_counts[pattern_type] = count

        total_patterns = sum(pattern_counts.values())
        text_length = len(text.split())

        if text_length == 0:
            return 0.0

        # Higher reasoning complexity for conditional and exception patterns
        complexity_weights = {
            'causal': 0.2,
            'conditional': 0.4,
            'comparative': 0.3,
            'exception': 0.5
        }

        weighted_complexity = sum(
            pattern_counts[pattern] * weight
            for pattern, weight in complexity_weights.items()
        )

        return min(1.0, weighted_complexity / text_length * 50)

    def _analyze_vocabulary_complexity(self, text: str) -> float:
        """
        Analyze vocabulary complexity
        """
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0.0

        # Calculate average word length
        avg_word_length = sum(len(word) for word in words) / len(words)

        # Count complex words (6+ characters)
        complex_words = [word for word in words if len(word) >= 6]
        complex_ratio = len(complex_words) / len(words)

        # Vocabulary diversity (unique words / total words)
        vocabulary_diversity = len(set(words)) / len(words)

        # Combined score
        complexity_score = (
            (avg_word_length / 10) * 0.3 +
            complex_ratio * 0.4 +
            (1 - vocabulary_diversity) * 0.3  # Lower diversity = more repetitive = easier
        )

        return min(1.0, complexity_score)

    def _calculate_overall_difficulty(self, metrics: Dict[str, Any]) -> DifficultyLevel:
        """
        Calculate overall difficulty level from metrics
        """
        # Weight different factors
        weights = {
            'readability_score': -0.3,  # Negative because higher readability = easier
            'legal_complexity': 0.25,
            'sentence_complexity': 0.2,
            'concept_density': 0.15,
            'reasoning_complexity': 0.25,
            'vocabulary_complexity': 0.15
        }

        total_score = sum(
            metrics.get(factor, 0) * weight
            for factor, weight in weights.items()
        )

        # Map to difficulty levels
        if total_score <= 0.3:
            return DifficultyLevel.EASY
        elif total_score <= 0.6:
            return DifficultyLevel.MODERATE
        else:
            return DifficultyLevel.DIFFICULT

    def _extract_question_text(self, question: Dict[str, Any]) -> str:
        """
        Extract text content from generated question for analysis
        """
        text_parts = []

        # Extract based on question type
        if 'question_text' in question:
            text_parts.append(question['question_text'])

        if 'assertion' in question:
            text_parts.append(question['assertion'])

        if 'reason' in question:
            text_parts.append(question['reason'])

        if 'list_I' in question:
            text_parts.extend(question['list_I'])

        if 'list_II' in question:
            text_parts.extend(question['list_II'])

        if 'passage' in question:
            text_parts.append(question['passage'])

        return ' '.join(text_parts)

    def _analyze_question_complexity(self, question_text: str) -> Dict[str, Any]:
        """
        Analyze complexity of generated question text
        """
        return {
            'readability_score': self._calculate_readability(question_text),
            'legal_complexity': self._analyze_legal_complexity(question_text.lower()),
            'sentence_complexity': self._analyze_sentence_complexity(question_text),
            'vocabulary_complexity': self._analyze_vocabulary_complexity(question_text.lower()),
            'reasoning_complexity': self._analyze_reasoning_patterns(question_text.lower()),
            'overall_difficulty': DifficultyLevel.EASY
        }

    def _average_difficulty_score(self, difficulty_analyses: List[Dict[str, Any]]) -> float:
        """
        Calculate average difficulty score from multiple analyses
        """
        if not difficulty_analyses:
            return 0.5

        # Convert difficulty levels to numeric scores
        difficulty_map = {
            DifficultyLevel.EASY: 0.3,
            DifficultyLevel.MODERATE: 0.6,
            DifficultyLevel.DIFFICULT: 0.9
        }

        total_score = sum(
            difficulty_map.get(analysis['overall_difficulty'], 0.5)
            for analysis in difficulty_analyses
        )

        return total_score / len(difficulty_analyses)

    def _calculate_alignment_score(
        self,
        question_metrics: Dict[str, Any],
        source_difficulty: float,
        target_difficulty: DifficultyLevel
    ) -> float:
        """
        Calculate how well the question aligns with target difficulty
        """
        # Map target difficulty to numeric score
        difficulty_map = {
            DifficultyLevel.EASY: 0.3,
            DifficultyLevel.MODERATE: 0.6,
            DifficultyLevel.DIFFICULT: 0.9
        }

        target_score = difficulty_map[target_difficulty]

        # Calculate question difficulty score
        question_score = self._average_difficulty_score([question_metrics])

        # Alignment based on how close scores are
        score_difference = abs(question_score - target_score)
        source_alignment = 1 - abs(source_difficulty - target_score)

        # Combined alignment score
        alignment = (
            (1 - score_difference) * 0.6 +  # Question-target alignment
            source_alignment * 0.4  # Source-target alignment
        )

        return max(0, min(1, alignment))

    def _generate_recommendations(
        self,
        question_metrics: Dict[str, Any],
        target_difficulty: DifficultyLevel,
        alignment_score: float
    ) -> List[str]:
        """
        Generate recommendations for improving question difficulty alignment
        """
        recommendations = []

        if alignment_score < 0.7:
            if target_difficulty == DifficultyLevel.EASY:
                recommendations.extend([
                    "Simplify vocabulary and use more direct language",
                    "Use clearer concept-definition relationships",
                    "Reduce sentence complexity and clause nesting"
                ])
            elif target_difficulty == DifficultyLevel.MODERATE:
                recommendations.extend([
                    "Add some contradictory or exception-based language",
                    "Include moderate legal terminology",
                    "Use conditional or comparative reasoning patterns"
                ])
            else:  # DIFFICULT
                recommendations.extend([
                    "Increase legal terminology complexity",
                    "Add multiple layers of reasoning",
                    "Include exception handling and nuanced distinctions"
                ])

        return recommendations


# Singleton instance
difficulty_analyzer = DifficultyAnalyzer()