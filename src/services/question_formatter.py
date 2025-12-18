"""
Minimal LLM Formatting Layer for Question Generation
Polishes Neo4j-generated questions to be human-readable and student-friendly.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from utils.llm_client import LlmClient
from services.assertion_reasoning_builder import ARQuestionData
from services.match_following_builder import MFQuestionData
from models.question_models import DifficultyLevel

logger = logging.getLogger(__name__)


@dataclass
class FormattedQuestion:
    """Formatted question ready for UGC NET"""
    question_text: str
    content: Dict[str, Any]
    explanation: str
    estimated_time: int


class QuestionFormatter:
    """
    Minimal LLM layer to make Neo4j-generated questions human-readable
    """

    def __init__(self):
        self.llm_client = LlmClient()

    def format_assertion_reasoning(self, ar_data: ARQuestionData) -> FormattedQuestion:
        """Format assertion-reasoning question for human readability"""

        try:
            # Minimal LLM prompt for polishing
            prompt = f"""
            Polish this UGC NET assertion-reasoning question for students. Keep legal accuracy but make language clear and accessible.

            Raw Assertion: {ar_data.assertion}
            Raw Reason: {ar_data.reason}
            Difficulty: {ar_data.difficulty.value}

            Requirements:
            1. Make language student-friendly but legally accurate
            2. Ensure proper grammar and clarity
            3. Keep statements concise and clear
            4. Don't change legal facts or concepts

            Return ONLY the polished assertion and reason, separated by "|||":
            Polished Assertion|||Polished Reason
            """

            response = self.llm_client.generate_answer(prompt, [])

            # Parse response
            if "|||" in response:
                parts = response.split("|||")
                polished_assertion = parts[0].strip()
                polished_reason = parts[1].strip()
            else:
                # Fallback to original if parsing fails
                polished_assertion = ar_data.assertion
                polished_reason = ar_data.reason
                logger.warning("Failed to parse LLM formatting response")

            # Enhanced explanation
            enhanced_explanation = self._enhance_explanation(ar_data.explanation, ar_data.difficulty)

            # Build formatted content
            content = {
                "assertion": f"Assertion (A): {polished_assertion}",
                "reason": f"Reason (R): {polished_reason}",
                "options": [
                    "Both A and R are true and R is the correct explanation of A.",
                    "Both A and R are true but R is not the correct explanation of A.",
                    "A is true but R is false.",
                    "A is false but R is true."
                ],
                "correct_option": ar_data.correct_option,
                "explanation": enhanced_explanation,
                "difficulty": ar_data.difficulty,
                "source_chunks": ar_data.source_chunks
            }

            return FormattedQuestion(
                question_text="Read the following statements about constitutional law and select the correct option:",
                content=content,
                explanation=enhanced_explanation,
                estimated_time=self._estimate_time(ar_data.difficulty)
            )

        except Exception as e:
            logger.error(f"Failed to format assertion-reasoning question: {e}")
            return self._fallback_ar_formatting(ar_data)

    def format_match_following(self, mf_data: MFQuestionData) -> FormattedQuestion:
        """Format match-the-following question for human readability"""

        try:
            # Minimal LLM prompt for polishing
            list_I_text = ", ".join(mf_data.list_I)
            list_II_text = ", ".join(mf_data.list_II)

            prompt = f"""
            Polish these legal concepts for a UGC NET match-the-following question. Make them clear and student-friendly.

            List I concepts: {list_I_text}
            List II definitions: {list_II_text}
            Difficulty: {mf_data.difficulty.value}

            Requirements:
            1. Make language accessible but legally accurate
            2. Ensure proper formatting and clarity
            3. Keep legal terminology correct
            4. Don't change meanings or facts

            Return ONLY the polished lists in this format:
            LIST_I: item1|||item2|||item3|||item4
            LIST_II: def1|||def2|||def3|||def4
            """

            response = self.llm_client.generate_answer(prompt, [])

            # Parse response
            polished_list_I = mf_data.list_I  # Default fallback
            polished_list_II = mf_data.list_II  # Default fallback

            if "LIST_I:" in response and "LIST_II:" in response:
                lines = response.split("\n")
                for line in lines:
                    if line.startswith("LIST_I:"):
                        items = line.replace("LIST_I:", "").strip().split("|||")
                        if len(items) == 4:
                            polished_list_I = [item.strip() for item in items]
                    elif line.startswith("LIST_II:"):
                        items = line.replace("LIST_II:", "").strip().split("|||")
                        if len(items) == 4:
                            polished_list_II = [item.strip() for item in items]

            # Enhanced explanation
            enhanced_explanation = self._enhance_explanation(mf_data.explanation, mf_data.difficulty)

            # Build formatted content
            content = {
                "list_I": polished_list_I,
                "list_II": polished_list_II,
                "correct_matches": mf_data.correct_matches,
                "explanation": enhanced_explanation,
                "difficulty": mf_data.difficulty,
                "source_chunks": mf_data.source_chunks
            }

            return FormattedQuestion(
                question_text="Match List I with List II and select the correct answer from the options given below:",
                content=content,
                explanation=enhanced_explanation,
                estimated_time=self._estimate_time(mf_data.difficulty)
            )

        except Exception as e:
            logger.error(f"Failed to format match-following question: {e}")
            return self._fallback_mf_formatting(mf_data)

    def _enhance_explanation(self, base_explanation: str, difficulty: DifficultyLevel) -> str:
        """Enhance explanation with LLM for better student understanding"""

        try:
            prompt = f"""
            Enhance this explanation for UGC NET students. Make it educational and clear.

            Original explanation: {base_explanation}
            Difficulty level: {difficulty.value}

            Requirements:
            1. Keep under 150 words
            2. Make it educational and informative
            3. Reference constitutional principles where relevant
            4. Use student-friendly language
            5. Include why other options might be tempting but incorrect

            Return only the enhanced explanation:
            """

            enhanced = self.llm_client.generate_answer(prompt, [])

            # Validate response length
            if len(enhanced) > 500:  # Too long
                enhanced = enhanced[:500] + "..."

            return enhanced.strip()

        except Exception as e:
            logger.warning(f"Failed to enhance explanation: {e}")
            return base_explanation

    def _estimate_time(self, difficulty: DifficultyLevel) -> int:
        """Estimate time in minutes based on difficulty"""
        time_mapping = {
            DifficultyLevel.EASY: 2,
            DifficultyLevel.MODERATE: 3,
            DifficultyLevel.DIFFICULT: 4
        }
        return time_mapping.get(difficulty, 3)

    def _fallback_ar_formatting(self, ar_data: ARQuestionData) -> FormattedQuestion:
        """Fallback formatting without LLM for assertion-reasoning"""
        content = {
            "assertion": f"Assertion (A): {ar_data.assertion}",
            "reason": f"Reason (R): {ar_data.reason}",
            "options": [
                "Both A and R are true and R is the correct explanation of A.",
                "Both A and R are true but R is not the correct explanation of A.",
                "A is true but R is false.",
                "A is false but R is true."
            ],
            "correct_option": ar_data.correct_option,
            "explanation": ar_data.explanation,
            "difficulty": ar_data.difficulty,
            "source_chunks": ar_data.source_chunks
        }

        return FormattedQuestion(
            question_text="Read the following statements about constitutional law and select the correct option:",
            content=content,
            explanation=ar_data.explanation,
            estimated_time=self._estimate_time(ar_data.difficulty)
        )

    def _fallback_mf_formatting(self, mf_data: MFQuestionData) -> FormattedQuestion:
        """Fallback formatting without LLM for match-following"""
        content = {
            "list_I": mf_data.list_I,
            "list_II": mf_data.list_II,
            "correct_matches": mf_data.correct_matches,
            "explanation": mf_data.explanation,
            "difficulty": mf_data.difficulty,
            "source_chunks": mf_data.source_chunks
        }

        return FormattedQuestion(
            question_text="Match List I with List II and select the correct answer from the options given below:",
            content=content,
            explanation=mf_data.explanation,
            estimated_time=self._estimate_time(mf_data.difficulty)
        )

    def format_simple_text(self, text: str, context: str = "") -> str:
        """Simple text formatting for any content"""
        try:
            prompt = f"""
            Make this text student-friendly and clear for UGC NET preparation:

            Text: {text}
            Context: {context}

            Requirements:
            1. Keep legal accuracy
            2. Make language accessible
            3. Proper grammar and formatting
            4. Keep concise

            Return only the formatted text:
            """

            formatted = self.llm_client.generate_answer(prompt, [])
            return formatted.strip()

        except Exception as e:
            logger.warning(f"Failed to format text: {e}")
            return text

    def validate_question_quality(self, question: FormattedQuestion) -> Dict[str, Any]:
        """Validate question quality and provide feedback"""
        validation = {
            "is_valid": True,
            "issues": [],
            "quality_score": 0.8,  # Default score
            "recommendations": []
        }

        # Check question text length
        if len(question.question_text) < 20:
            validation["issues"].append("Question text too short")
            validation["quality_score"] -= 0.2

        # Check explanation quality
        if len(question.explanation) < 50:
            validation["issues"].append("Explanation too brief")
            validation["quality_score"] -= 0.1

        # Check if content has required fields
        required_fields = ["explanation", "difficulty"]
        for field in required_fields:
            if field not in question.content:
                validation["issues"].append(f"Missing required field: {field}")
                validation["quality_score"] -= 0.2

        # Set final validation status
        validation["is_valid"] = len(validation["issues"]) == 0 and validation["quality_score"] > 0.6

        return validation


# Singleton instance
question_formatter = QuestionFormatter()