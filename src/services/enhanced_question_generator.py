"""
Enhanced Question Generator Service for UGC NET Exam Preparation
Leverages Neo4j knowledge graphs for intelligent question generation with difficulty calibration.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.question_models import (
    QuestionGenerationRequest, QuestionGenerationResponse, QuestionType,
    DifficultyLevel, QuestionRequest, GeneratedQuestion, QuestionMetadata,
    AssertionReasonQuestion, MatchFollowingQuestion, ComprehensionQuestion,
    QuestionFilters
)
from services.content_selector import content_selector
from utils.difficulty_analyzer import difficulty_analyzer
from utils.llm_client import LlmClient

logger = logging.getLogger(__name__)


class EnhancedQuestionGenerator:
    """
    Advanced question generator that uses Neo4j graph intelligence and difficulty analysis
    for creating UGC NET exam-style questions
    """

    def __init__(self):
        self.llm_client = LlmClient()
        self.generated_questions_cache = set()  # For duplicate prevention

    async def generate_questions(self, request: QuestionGenerationRequest) -> QuestionGenerationResponse:
        """
        Main method to generate questions based on request specifications
        """
        try:
            all_questions = []
            generation_stats = {
                'total_requested': sum(q.count for q in request.questions),
                'by_type': {},
                'by_difficulty': {},
                'content_selection_time': 0,
                'generation_time': 0,
                'validation_time': 0
            }
            errors = []
            warnings = []

            # Process each question request
            for question_request in request.questions:
                try:
                    questions = await self._generate_question_batch(
                        question_request, request.context, generation_stats
                    )
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

                except Exception as e:
                    error_msg = f"Failed to generate {question_request.type.value} questions: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Validate and finalize response
            success = len(all_questions) > 0
            if len(all_questions) < generation_stats['total_requested']:
                warnings.append(
                    f"Generated {len(all_questions)} questions, "
                    f"requested {generation_stats['total_requested']}"
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
            logger.error(f"Question generation failed: {e}")
            return QuestionGenerationResponse(
                success=False,
                total_generated=0,
                questions=[],
                errors=[f"Generation failed: {str(e)}"]
            )

    async def generate_mixed_quiz(self, collection_id: str, count: int = 15, difficulty: DifficultyLevel = DifficultyLevel.MODERATE) -> QuestionGenerationResponse:
        """
        Generate a balanced mixed quiz for a collection
        """
        # Distribute question counts (e.g., 40% MCQ, 30% AR, 30% Match)
        mcq_count = int(count * 0.4)
        ar_count = int(count * 0.3)
        match_count = count - mcq_count - ar_count

        requests = []
        if mcq_count > 0:
            requests.append(QuestionRequest(
                type=QuestionType.MCQ,
                count=mcq_count,
                difficulty=difficulty,
                filters=QuestionFilters(collection_ids=[collection_id])
            ))
        if ar_count > 0:
            requests.append(QuestionRequest(
                type=QuestionType.ASSERTION_REASONING,
                count=ar_count,
                difficulty=difficulty,
                filters=QuestionFilters(collection_ids=[collection_id])
            ))
        if match_count > 0:
            requests.append(QuestionRequest(
                type=QuestionType.MATCH_FOLLOWING,
                count=match_count,
                difficulty=difficulty,
                filters=QuestionFilters(collection_ids=[collection_id])
            ))

        req = QuestionGenerationRequest(questions=requests)
        return await self.generate_questions(req)

    async def _generate_question_batch(
        self,
        question_request: QuestionRequest,
        context,
        stats: Dict[str, Any]
    ) -> List[GeneratedQuestion]:
        """
        Generate a batch of questions for a specific type and difficulty
        """
        questions = []

        # Select appropriate content
        start_time = datetime.now()
        content_result = content_selector.select_content_for_question(
            question_request.type,
            question_request.difficulty,
            question_request.filters,
            question_request.count
        )
        stats['content_selection_time'] += (datetime.now() - start_time).total_seconds()

        if not content_result.selected_chunks:
            logger.warning(f"No content found for {question_request.type.value} questions")
            return questions

        logger.info(f"Found {len(content_result.selected_chunks)} chunks for {question_request.type.value} questions")

        # Generate questions based on type
        start_time = datetime.now()

        if question_request.type == QuestionType.ASSERTION_REASONING:
            questions = await self._generate_assertion_reasoning_batch(
                question_request, content_result, context
            )
        elif question_request.type == QuestionType.MATCH_FOLLOWING:
            questions = await self._generate_match_following_batch(
                question_request, content_result, context
            )
        elif question_request.type == QuestionType.COMPREHENSION:
            questions = await self._generate_comprehension_batch(
                question_request, content_result, context
            )
        elif question_request.type == QuestionType.MCQ:
            questions = await self._generate_mcq_batch(
                question_request, content_result, context
            )

        stats['generation_time'] += (datetime.now() - start_time).total_seconds()

        # Validate difficulty and quality
        start_time = datetime.now()
        validated_questions = self._validate_and_filter_questions(
            questions, question_request, content_result
        )
        stats['validation_time'] += (datetime.now() - start_time).total_seconds()

        return validated_questions

    async def _generate_assertion_reasoning_batch(
        self,
        request: QuestionRequest,
        content_result,
        context
    ) -> List[GeneratedQuestion]:
        """
        Generate assertion-reasoning questions using selected content
        """
        questions = []

        # Group chunks for batch processing
        chunk_groups = self._group_chunks_for_assertion_reasoning(
            content_result.selected_chunks, request.count
        )

        for chunk_group in chunk_groups:
            prompt = self._build_assertion_reasoning_prompt(
                chunk_group, request.difficulty, context
            )

            try:
                # Pass chunk content as context
                context_chunks = [chunk.text for chunk in chunk_group]
                response = self.llm_client.generate_answer(prompt, context_chunks, force_json=True)
                question_data = self._parse_json_response(response)

                if question_data and not self._is_duplicate(question_data):
                    question = self._create_assertion_reasoning_question(
                        question_data, request.difficulty, chunk_group
                    )
                    questions.append(question)
                    self.generated_questions_cache.add(self._get_question_hash(question_data))

            except Exception as e:
                logger.error(f"Failed to generate assertion-reasoning question: {e}")

        return questions

    async def _generate_match_following_batch(
        self,
        request: QuestionRequest,
        content_result,
        context
    ) -> List[GeneratedQuestion]:
        """
        Generate match-the-following questions using selected content
        """
        questions = []

        # Group chunks for match-following generation
        chunk_groups = self._group_chunks_for_match_following(
            content_result.selected_chunks, request.count
        )

        for chunk_group in chunk_groups:
            prompt = self._build_match_following_prompt(
                chunk_group, request.difficulty, context
            )

            try:
                # Pass chunk content as context
                context_chunks = [chunk.text for chunk in chunk_group]
                response = self.llm_client.generate_answer(prompt, context_chunks, force_json=True)
                question_data = self._parse_json_response(response)

                if question_data and not self._is_duplicate(question_data):
                    question = self._create_match_following_question(
                        question_data, request.difficulty, chunk_group
                    )
                    questions.append(question)
                    self.generated_questions_cache.add(self._get_question_hash(question_data))

            except Exception as e:
                logger.error(f"Failed to generate match-following question: {e}")

        return questions

    async def _generate_mcq_batch(
        self,
        request: QuestionRequest,
        content_result,
        context
    ) -> List[GeneratedQuestion]:
        """
        Generate standard multiple choice questions using selected content
        """
        questions = []
        
        logger.info(f"Starting MCQ batch generation: requested={request.count}, available_chunks={len(content_result.selected_chunks)}")

        # Each chunk can typically yield one good MCQ
        for idx, chunk in enumerate(content_result.selected_chunks[:request.count]):
            logger.info(f"Processing MCQ {idx+1}/{min(request.count, len(content_result.selected_chunks))}, chunk_id={chunk.chunk_id}")
            
            prompt = self._build_mcq_prompt(
                chunk, request.difficulty, context
            )

            try:
                context_chunks = [chunk.text]
                logger.info(f"Sending MCQ prompt to LLM for chunk {chunk.chunk_id}")
                response = self.llm_client.generate_answer(prompt, context_chunks, force_json=True)
                logger.info(f"Received LLM response for MCQ {idx+1}, length={len(response)}")
                
                question_data = self._parse_json_response(response)
                
                if not question_data:
                    logger.warning(f"Failed to parse JSON response for MCQ {idx+1}")
                    logger.debug(f"Raw response: {response[:500]}")
                    continue
                
                if self._is_duplicate(question_data):
                    logger.warning(f"MCQ {idx+1} is a duplicate, skipping")
                    continue
                
                logger.info(f"Creating MCQ question object for {idx+1}")
                question = self._create_mcq_question(
                    question_data, request.difficulty, [chunk]
                )
                questions.append(question)
                self.generated_questions_cache.add(self._get_question_hash(question_data))
                logger.info(f"Successfully generated MCQ {idx+1}")

            except Exception as e:
                logger.error(f"Failed to generate MCQ question {idx+1}: {e}", exc_info=True)

        logger.info(f"MCQ batch generation complete: generated={len(questions)}, requested={request.count}")
        return questions

    async def _generate_comprehension_batch(
        self,
        request: QuestionRequest,
        content_result,
        context
    ) -> List[GeneratedQuestion]:
        """
        Generate comprehension questions using selected content
        """
        questions = []

        # Use individual chunks as passages for comprehension
        for chunk in content_result.selected_chunks[:request.count]:
            prompt = self._build_comprehension_prompt(
                chunk, request.difficulty, context
            )

            try:
                # Pass chunk content as context
                context_chunks = [chunk.text]
                response = self.llm_client.generate_answer(prompt, context_chunks, force_json=True)
                question_data = self._parse_json_response(response)

                if question_data and not self._is_duplicate(question_data):
                    question = self._create_comprehension_question(
                        question_data, request.difficulty, [chunk]
                    )
                    questions.append(question)
                    self.generated_questions_cache.add(self._get_question_hash(question_data))

            except Exception as e:
                logger.error(f"Failed to generate comprehension question: {e}")

        return questions

    def _build_assertion_reasoning_prompt(
        self,
        chunks,
        difficulty: DifficultyLevel,
        context
    ) -> str:
        """
        Build UGC NET-specific prompt for assertion-reasoning questions
        """
        chunks_text = "\n".join([f"Chunk {i+1}: {chunk.text[:800]}" for i, chunk in enumerate(chunks)])

        difficulty_instructions = {
            DifficultyLevel.EASY: """
            - Create straightforward assertion and reason statements
            - Use direct, clear language with basic legal concepts
            - The relationship should be obvious and factual
            """,
            DifficultyLevel.MODERATE: """
            - Include some complexity with conditional language
            - Use moderate legal terminology and concepts
            - The relationship should require some analysis but be determinable
            """,
            DifficultyLevel.DIFFICULT: """
            - Use complex legal principles with nuanced relationships
            - Include exceptions, limitations, or contradictory elements
            - Require deep constitutional/legal reasoning to determine the relationship
            """
        }

        prompt = f"""
        Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
        Task: Create a high-quality "Assertion-Reason" question for UGC NET Paper-II.

        Difficulty Level: {difficulty.value.upper()}
        Subject Area: {context.subject if context else 'Law'}

        {difficulty_instructions[difficulty]}

        Source Legal Content:
        {chunks_text}

        UGC NET Assertion-Reason Format Requirements:
        1. Create a clear, legally accurate assertion statement
        2. Create a related reason that may or may not correctly explain the assertion
        3. Both statements must be factually verifiable from constitutional/legal principles
        4. Use standard UGC NET options format exactly as provided

        Standard UGC NET Options (use exactly these):
        1. "Both A and R are true and R is the correct explanation of A."
        2. "Both A and R are true but R is not the correct explanation of A."
        3. "A is true but R is false."
        4. "A is false but R is true."

        Output JSON format:
        {{
            "question_text": "Read the following statements about constitutional law and select the correct option:",
            "assertion": "Assertion (A): [Clear legal principle or constitutional provision]",
            "reason": "Reason (R): [Related explanation, context, or supporting principle]",
            "options": [
                "Both A and R are true and R is the correct explanation of A.",
                "Both A and R are true but R is not the correct explanation of A.",
                "A is true but R is false.",
                "A is false but R is true."
            ],
            "correct_option": "[Exact option text from above]",
            "explanation": "Detailed explanation referencing constitutional provisions, case law, or legal principles. Explain why each part of the assertion and reason is true/false and why the relationship is/isn't correct."
        }}
        """

        return prompt

    def _build_match_following_prompt(
        self,
        chunks,
        difficulty: DifficultyLevel,
        context
    ) -> str:
        """
        Build UGC NET-specific prompt for match-the-following questions
        """
        chunks_text = "\n".join([f"Chunk {i+1}: {chunk.text[:600]}" for i, chunk in enumerate(chunks)])

        difficulty_instructions = {
            DifficultyLevel.EASY: """
            - Use direct concept-definition or case-outcome relationships
            - Clear, unambiguous matches with basic legal terminology
            - Factual relationships that are straightforward
            """,
            DifficultyLevel.MODERATE: """
            - Include case law, statutory provisions, and their applications
            - Some complexity in relationships (cause-effect, principle-application)
            - Require good understanding of legal concepts
            """,
            DifficultyLevel.DIFFICULT: """
            - Complex legal principles with multiple related concepts
            - Advanced constitutional doctrines, judicial precedents
            - Subtle relationships requiring deep legal knowledge
            """
        }

        prompt = f"""
        Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
        Task: Create a "Match the Following" question for UGC NET Paper-II.

        Difficulty Level: {difficulty.value.upper()}
        Subject Area: {context.subject if context else 'Law'}

        {difficulty_instructions[difficulty]}

        Source Legal Content:
        {chunks_text}

        UGC NET Match the Following Requirements:
        1. Create exactly 4 items in List I and 4 items in List II
        2. Each item in List I should have exactly one correct match in List II
        3. Ensure all matches are factually accurate and legally sound
        4. Use proper legal terminology and constitutional references

        Output JSON format:
        {{
            "question_text": "Match List I with List II and select the correct answer from the options given below:",
            "list_I": [
                "Legal Concept/Case/Provision 1",
                "Legal Concept/Case/Provision 2",
                "Legal Concept/Case/Provision 3",
                "Legal Concept/Case/Provision 4"
            ],
            "list_II": [
                "Definition/Outcome/Application A",
                "Definition/Outcome/Application B",
                "Definition/Outcome/Application C",
                "Definition/Outcome/Application D"
            ],
            "correct_matches": {{
                "Legal Concept/Case/Provision 1": "Definition/Outcome/Application A",
                "Legal Concept/Case/Provision 2": "Definition/Outcome/Application B",
                "Legal Concept/Case/Provision 3": "Definition/Outcome/Application C",
                "Legal Concept/Case/Provision 4": "Definition/Outcome/Application D"
            }},
            "explanation": "Detailed explanation of each correct match with constitutional/legal basis. Reference specific articles, cases, or legal principles that establish these relationships."
        }}
        """

        return prompt

    def _build_mcq_prompt(
        self,
        chunk,
        difficulty: DifficultyLevel,
        context
    ) -> str:
        """
        Build UGC NET-specific prompt for standard MCQ questions
        """
        difficulty_instructions = {
            DifficultyLevel.EASY: """
            - Focus on basic concepts, definitions, and direct factual recall
            - Clear, unambiguous options
            """,
            DifficultyLevel.MODERATE: """
            - Require application of principles or understanding of relationships
            - Use plausible distractors that require careful reading to eliminate
            """,
            DifficultyLevel.DIFFICULT: """
            - Complex analytical questions involving multiple principles
            - Subtle distinctions between options requiring deep legal knowledge
            """
        }

        prompt = f"""
        Role: UGC NET Legal Exam Setter specializing in Law.
        Task: Create a high-quality Multiple Choice Question (MCQ) for UGC NET Paper-II.

        Difficulty Level: {difficulty.value.upper()}
        Subject Area: {context.subject if context else 'Law'}

        {difficulty_instructions[difficulty]}

        Source Content:
        {chunk.text}

        Requirements:
        1. Base the question strictly on the provided content
        2. Create 4 options (A, B, C, D) with only one correct answer
        3. Ensure the question is professionally phrased and student-friendly

        Output JSON format:
        {{
            "question_text": "The clear and complete question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": "The exact text of the correct option",
            "explanation": "Detailed professional explanation referencing the legal principles"
        }}
        """
        return prompt

    def _build_comprehension_prompt(
        self,
        chunk,
        difficulty: DifficultyLevel,
        context
    ) -> str:
        """
        Build UGC NET-specific prompt for comprehension questions
        """
        difficulty_instructions = {
            DifficultyLevel.EASY: """
            - Direct questions testing basic understanding and factual recall
            - Clear questions with obvious answers from the passage
            - Simple inference and application questions
            """,
            DifficultyLevel.MODERATE: """
            - Questions requiring analysis and interpretation
            - Some implicit information requiring inference
            - Application of legal principles to given scenarios
            """,
            DifficultyLevel.DIFFICULT: """
            - Complex analytical and evaluative questions
            - Multiple layers of reasoning required
            - Critical analysis of legal implications and consequences
            """
        }

        prompt = f"""
        Role: UGC NET Legal Exam Setter specializing in Constitutional and Administrative Law.
        Task: Create a comprehension passage with 3 questions for UGC NET Paper-II.

        Difficulty Level: {difficulty.value.upper()}
        Subject Area: {context.subject if context else 'Law'}

        {difficulty_instructions[difficulty]}

        Source Legal Passage:
        {chunk.text}

        UGC NET Comprehension Requirements:
        1. Use the provided text as the passage (may edit for clarity/length)
        2. Create exactly 3 multiple choice questions based on the passage
        3. Each question should have 4 options with only one correct answer
        4. Questions should test: (a) factual understanding, (b) inference/analysis, (c) application/implication

        Output JSON format:
        {{
            "passage": "Legal passage text (edited for clarity if needed, 300-500 words)",
            "questions": [
                {{
                    "question_text": "Question 1 testing factual understanding from passage",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_option": "Option A",
                    "explanation": "Explanation with reference to specific part of passage"
                }},
                {{
                    "question_text": "Question 2 requiring inference or analysis",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_option": "Option B",
                    "explanation": "Explanation with analytical reasoning"
                }},
                {{
                    "question_text": "Question 3 testing application or implication",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_option": "Option C",
                    "explanation": "Explanation with legal application reasoning"
                }}
            ]
        }}
        """

        return prompt

    def _group_chunks_for_assertion_reasoning(self, chunks, count: int):
        """Group chunks appropriately for assertion-reasoning questions"""
        # Use 2-3 chunks per question for better context
        groups = []
        for i in range(0, min(len(chunks), count * 3), 2):
            group = chunks[i:i+2]
            if len(group) >= 1:  # At least 1 chunk needed
                groups.append(group)
        return groups[:count]

    def _group_chunks_for_match_following(self, chunks, count: int):
        """Group chunks appropriately for match-following questions"""
        # Use 4-6 chunks per question to extract enough concepts
        groups = []
        for i in range(0, min(len(chunks), count * 6), 4):
            group = chunks[i:i+6]
            if len(group) >= 4:  # Need at least 4 chunks for 4 matches
                groups.append(group)
        return groups[:count]

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM JSON response with error handling"""
        try:
            # Clean response if it has markdown formatting
            clean_response = response.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None

    def _is_duplicate(self, question_data: Dict[str, Any]) -> bool:
        """Check if question is a duplicate of previously generated ones"""
        question_hash = self._get_question_hash(question_data)
        is_dup = question_hash in self.generated_questions_cache
        if is_dup:
            logger.debug(f"Duplicate detected with hash: {question_hash}")
        return is_dup

    def _get_question_hash(self, question_data: Dict[str, Any]) -> str:
        """Generate a hash for duplicate detection"""
        # Create hash from key question elements
        hash_elements = []

        # MCQ questions
        if 'question_text' in question_data:
            hash_elements.append(question_data['question_text'][:150])
        if 'options' in question_data:
            hash_elements.extend([opt[:50] for opt in question_data['options'][:2]])  # First 2 options
        
        # Assertion-Reasoning questions
        if 'assertion' in question_data:
            hash_elements.append(question_data['assertion'][:100])
        if 'reason' in question_data:
            hash_elements.append(question_data['reason'][:100])
        
        # Match the Following questions
        if 'list_I' in question_data:
            hash_elements.extend(question_data['list_I'])
        
        # Comprehension questions
        if 'passage' in question_data:
            hash_elements.append(question_data['passage'][:200])

        return str(hash(str(hash_elements)))

    def _create_assertion_reasoning_question(
        self,
        question_data: Dict[str, Any],
        difficulty: DifficultyLevel,
        chunks
    ) -> GeneratedQuestion:
        """Create AssertionReasonQuestion object with metadata"""

        question_content = AssertionReasonQuestion(
            question_text=question_data.get('question_text', ''),
            assertion=question_data.get('assertion', ''),
            reason=question_data.get('reason', ''),
            options=question_data.get('options', []),
            correct_option=question_data.get('correct_option', ''),
            explanation=question_data.get('explanation', ''),
            difficulty=difficulty,
            source_chunks=[chunk.chunk_id for chunk in chunks]
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.ASSERTION_REASONING,
            difficulty=difficulty,
            estimated_time=2 if difficulty == DifficultyLevel.EASY else 3 if difficulty == DifficultyLevel.MODERATE else 4,
            source_entities=[],
            source_files=list(set(chunk.file_id for chunk in chunks)),
            generated_at=datetime.now().isoformat()
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _create_match_following_question(
        self,
        question_data: Dict[str, Any],
        difficulty: DifficultyLevel,
        chunks
    ) -> GeneratedQuestion:
        """Create MatchFollowingQuestion object with metadata"""

        question_content = MatchFollowingQuestion(
            question_text=question_data.get('question_text', ''),
            list_I=question_data.get('list_I', []),
            list_II=question_data.get('list_II', []),
            correct_matches=question_data.get('correct_matches', {}),
            explanation=question_data.get('explanation', ''),
            difficulty=difficulty,
            source_chunks=[chunk.chunk_id for chunk in chunks]
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.MATCH_FOLLOWING,
            difficulty=difficulty,
            estimated_time=2 if difficulty == DifficultyLevel.EASY else 3 if difficulty == DifficultyLevel.MODERATE else 4,
            source_entities=[],
            source_files=list(set(chunk.file_id for chunk in chunks)),
            generated_at=datetime.now().isoformat()
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _create_mcq_question(
        self,
        question_data: Dict[str, Any],
        difficulty: DifficultyLevel,
        chunks
    ) -> GeneratedQuestion:
        """Create MultipleChoiceQuestion object with metadata"""
        from models.question_models import MultipleChoiceQuestion
        
        question_content = MultipleChoiceQuestion(
            question_text=question_data.get('question_text', ''),
            options=question_data.get('options', []),
            correct_option=question_data.get('correct_option', ''),
            explanation=question_data.get('explanation', ''),
            difficulty=difficulty,
            source_chunks=[chunk.chunk_id for chunk in chunks]
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.MCQ,
            difficulty=difficulty,
            estimated_time=1 if difficulty == DifficultyLevel.EASY else 2,
            source_entities=[],
            source_files=list(set(chunk.file_id for chunk in chunks)),
            generated_at=datetime.now().isoformat()
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _create_comprehension_question(
        self,
        question_data: Dict[str, Any],
        difficulty: DifficultyLevel,
        chunks
    ) -> GeneratedQuestion:
        """Create ComprehensionQuestion object with metadata"""

        question_content = ComprehensionQuestion(
            passage=question_data.get('passage', ''),
            questions=question_data.get('questions', []),
            difficulty=difficulty,
            source_chunks=[chunk.chunk_id for chunk in chunks]
        )

        metadata = QuestionMetadata(
            question_id=str(uuid.uuid4()),
            type=QuestionType.COMPREHENSION,
            difficulty=difficulty,
            estimated_time=5 if difficulty == DifficultyLevel.EASY else 7 if difficulty == DifficultyLevel.MODERATE else 10,
            source_entities=[],
            source_files=list(set(chunk.file_id for chunk in chunks)),
            generated_at=datetime.now().isoformat()
        )

        return GeneratedQuestion(metadata=metadata, content=question_content)

    def _validate_and_filter_questions(
        self,
        questions: List[GeneratedQuestion],
        request: QuestionRequest,
        content_result
    ) -> List[GeneratedQuestion]:
        """Validate questions against difficulty and quality criteria"""
        validated_questions = []

        for question in questions:
            try:
                # Extract question content for validation
                question_dict = question.content.dict()

                # Validate difficulty alignment
                validation_result = difficulty_analyzer.validate_question_difficulty(
                    question_dict, request.difficulty, content_result.selected_chunks
                )

                if validation_result['is_valid']:
                    validated_questions.append(question)
                else:
                    logger.info(
                        f"Question filtered due to difficulty mismatch: "
                        f"target={request.difficulty.value}, "
                        f"actual={validation_result['question_difficulty']}"
                    )

            except Exception as e:
                logger.error(f"Question validation failed: {e}")

        return validated_questions[:request.count]  # Return up to requested count


# Singleton instance
enhanced_question_generator = EnhancedQuestionGenerator()