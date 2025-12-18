
import logging
import json
from typing import Dict, List
from services.graph_service import get_graph_service
from utils.llm_client import LlmClient

logger = logging.getLogger(__name__)

class QuestionGeneratorService:
    def __init__(self):
        self.llm_client = LlmClient()

    def generate_match_list(self, file_id: str = None) -> Dict:
        """
        Generates a 'Match List' question by extracting legal concepts from document chunks.
        """
        # Get relevant chunks with legal content
        query = """
        MATCH (c:Chunk)
        WHERE ($file_id IS NULL OR c.file_id = $file_id)
        AND c.chunk_type = 'concept'
        AND size(c.text) > 200
        WITH c
        ORDER BY rand()
        LIMIT 8
        RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = get_graph_service().execute_query(query, params)

        if not records or len(records) < 4:
            return {"error": "Not enough chunk data to generate a Match List question."}

        # Extract text content for LLM analysis
        chunks_data = []
        for r in records:
            chunks_data.append({
                "text": r["chunk_text"][:500],  # Limit text length
                "key_terms": r.get("key_terms", []),
                "chapter": r.get("chapter_title", "")
            })

        prompt = f"""
        Role: Legal Exam Setter specializing in Constitutional Law.
        Task: Create a "Match List" (Match the Following) question from legal document content.

        Source Content (Legal Document Chunks):
        {json.dumps(chunks_data, indent=2)}

        Instructions:
        1. Extract 4 distinct legal concepts, cases, statutes, or legal principles from the content
        2. For each concept, identify its corresponding definition, ruling, or explanation
        3. Create a proper Match List question with clear items and matches
        4. Ensure matches are based on actual legal relationships in the content

        Output format (JSON):
        {{
            "question_text": "Match List I with List II based on the legal concepts from constitutional law.",
            "list_I": ["Legal Concept A", "Case B", "Legal Principle C", "Constitutional Provision D"],
            "list_II": ["Definition/Explanation 1", "Ruling/Outcome 2", "Application 3", "Interpretation 4"],
            "correct_matches": {{"Legal Concept A": "Definition/Explanation 2", ...}},
            "explanation": "Brief explanation of why each match is correct based on constitutional law principles."
        }}
        """

        return self._generate_json(prompt)

    def generate_assertion_reason(self, file_id: str = None) -> Dict:
        """
        Generates 'Assertion-Reason' question by analyzing legal concepts in chunks for logical relationships.
        """
        # Get chunks with rich legal content that may contain contradictory or complementary concepts
        query = """
        MATCH (c:Chunk)
        WHERE ($file_id IS NULL OR c.file_id = $file_id)
        AND c.chunk_type = 'concept'
        AND size(c.text) > 300
        AND (c.text CONTAINS 'however' OR c.text CONTAINS 'but' OR c.text CONTAINS 'exception'
             OR c.text CONTAINS 'nevertheless' OR c.text CONTAINS 'although' OR c.text CONTAINS 'despite')
        WITH c
        ORDER BY rand()
        LIMIT 5
        RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = get_graph_service().execute_query(query, params)

        if not records:
            # Fallback to any concept chunks if no contradictory language found
            fallback_query = """
            MATCH (c:Chunk)
            WHERE ($file_id IS NULL OR c.file_id = $file_id)
            AND c.chunk_type = 'concept'
            AND size(c.text) > 200
            WITH c
            ORDER BY rand()
            LIMIT 5
            RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
            """
            records = get_graph_service().execute_query(fallback_query, params)

        if not records:
            return {"error": "No suitable content found for Assertion-Reason question generation."}

        # Prepare content for LLM analysis
        chunks_data = []
        for r in records:
            chunks_data.append({
                "text": r["chunk_text"][:800],  # More text for context
                "key_terms": r.get("key_terms", []),
                "chapter": r.get("chapter_title", "")
            })

        prompt = f"""
        Role: Legal Exam Setter specializing in Constitutional Law.
        Task: Create an "Assertion-Reason" question from legal document content.

        Source Content (Legal Document Chunks):
        {json.dumps(chunks_data, indent=2)}

        Instructions:
        1. Identify a key legal principle or constitutional concept from the content
        2. Find a related explanation, exception, limitation, or supporting argument
        3. Create an assertion that states the main principle
        4. Create a reason that provides explanation, limitation, or context
        5. Determine the correct logical relationship between assertion and reason

        Standard Options:
        - "Both A and R are true and R is the correct explanation of A."
        - "Both A and R are true but R is not the correct explanation of A."
        - "A is true but R is false."
        - "A is false but R is true."

        Output format (JSON):
        {{
            "question_text": "Read the following statements and choose the correct option.",
            "assertion": "Assertion (A): [Clear statement about a legal principle/concept]",
            "reason": "Reason (R): [Related explanation, context, or limitation]",
            "options": [
                "Both A and R are true and R is the correct explanation of A.",
                "Both A and R are true but R is not the correct explanation of A.",
                "A is true but R is false.",
                "A is false but R is true."
            ],
            "correct_option": "Both A and R are true but R is not the correct explanation of A.",
            "explanation": "Detailed explanation of why the correct option is right, referencing the constitutional law principles."
        }}
        """

        return self._generate_json(prompt)

    def _generate_json(self, prompt: str) -> Dict:
        response = self.llm_client.generate_answer(prompt, [], force_json=True)
        try:
            # Clean response if markdown blocks exist
            valid_json = response.replace('```json', '').replace('```', '').strip()
            return json.loads(valid_json)
        except json.JSONDecodeError:
            return {"error": "Failed to generate valid JSON", "raw_response": response}

question_generator = QuestionGeneratorService()


import logging
import json
from typing import Dict, List
from services.graph_service import graph_service
from utils.llm_client import LlmClient

logger = logging.getLogger(__name__)

class QuestionGeneratorService:
    def __init__(self):
        self.llm_client = LlmClient()

    def generate_match_list(self, file_id: str = None) -> Dict:
        """
        Generates a 'Match List' question by extracting legal concepts from document chunks.
        """
        # Get relevant chunks with legal content
        query = """
        MATCH (c:Chunk)
        WHERE ($file_id IS NULL OR c.file_id = $file_id)
        AND c.chunk_type = 'concept'
        AND size(c.text) > 200
        WITH c
        ORDER BY rand()
        LIMIT 8
        RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = graph_service.execute_query(query, params)

        if not records or len(records) < 4:
            return {"error": "Not enough chunk data to generate a Match List question."}

        # Extract text content for LLM analysis
        chunks_data = []
        for r in records:
            chunks_data.append({
                "text": r["chunk_text"][:500],  # Limit text length
                "key_terms": r.get("key_terms", []),
                "chapter": r.get("chapter_title", "")
            })

        prompt = f"""
        Role: Legal Exam Setter specializing in Constitutional Law.
        Task: Create a "Match List" (Match the Following) question from legal document content.

        Source Content (Legal Document Chunks):
        {json.dumps(chunks_data, indent=2)}

        Instructions:
        1. Extract 4 distinct legal concepts, cases, statutes, or legal principles from the content
        2. For each concept, identify its corresponding definition, ruling, or explanation
        3. Create a proper Match List question with clear items and matches
        4. Ensure matches are based on actual legal relationships in the content

        Output format (JSON):
        {{
            "question_text": "Match List I with List II based on the legal concepts from constitutional law.",
            "list_I": ["Legal Concept A", "Case B", "Legal Principle C", "Constitutional Provision D"],
            "list_II": ["Definition/Explanation 1", "Ruling/Outcome 2", "Application 3", "Interpretation 4"],
            "correct_matches": {{"Legal Concept A": "Definition/Explanation 2", ...}},
            "explanation": "Brief explanation of why each match is correct based on constitutional law principles."
        }}
        """

        return self._generate_json(prompt)

    def generate_assertion_reason(self, file_id: str = None) -> Dict:
        """
        Generates 'Assertion-Reason' question by analyzing legal concepts in chunks for logical relationships.
        """
        # Get chunks with rich legal content that may contain contradictory or complementary concepts
        query = """
        MATCH (c:Chunk)
        WHERE ($file_id IS NULL OR c.file_id = $file_id)
        AND c.chunk_type = 'concept'
        AND size(c.text) > 300
        AND (c.text CONTAINS 'however' OR c.text CONTAINS 'but' OR c.text CONTAINS 'exception'
             OR c.text CONTAINS 'nevertheless' OR c.text CONTAINS 'although' OR c.text CONTAINS 'despite')
        WITH c
        ORDER BY rand()
        LIMIT 5
        RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = graph_service.execute_query(query, params)

        if not records:
            # Fallback to any concept chunks if no contradictory language found
            fallback_query = """
            MATCH (c:Chunk)
            WHERE ($file_id IS NULL OR c.file_id = $file_id)
            AND c.chunk_type = 'concept'
            AND size(c.text) > 200
            WITH c
            ORDER BY rand()
            LIMIT 5
            RETURN c.text as chunk_text, c.key_terms as key_terms, c.chapter_title as chapter_title
            """
            records = graph_service.execute_query(fallback_query, params)

        if not records:
            return {"error": "No suitable content found for Assertion-Reason question generation."}

        # Prepare content for LLM analysis
        chunks_data = []
        for r in records:
            chunks_data.append({
                "text": r["chunk_text"][:800],  # More text for context
                "key_terms": r.get("key_terms", []),
                "chapter": r.get("chapter_title", "")
            })

        prompt = f"""
        Role: Legal Exam Setter specializing in Constitutional Law.
        Task: Create an "Assertion-Reason" question from legal document content.

        Source Content (Legal Document Chunks):
        {json.dumps(chunks_data, indent=2)}

        Instructions:
        1. Identify a key legal principle or constitutional concept from the content
        2. Find a related explanation, exception, limitation, or supporting argument
        3. Create an assertion that states the main principle
        4. Create a reason that provides explanation, limitation, or context
        5. Determine the correct logical relationship between assertion and reason

        Standard Options:
        - "Both A and R are true and R is the correct explanation of A."
        - "Both A and R are true but R is not the correct explanation of A."
        - "A is true but R is false."
        - "A is false but R is true."

        Output format (JSON):
        {{
            "question_text": "Read the following statements and choose the correct option.",
            "assertion": "Assertion (A): [Clear statement about a legal principle/concept]",
            "reason": "Reason (R): [Related explanation, context, or limitation]",
            "options": [
                "Both A and R are true and R is the correct explanation of A.",
                "Both A and R are true but R is not the correct explanation of A.",
                "A is true but R is false.",
                "A is false but R is true."
            ],
            "correct_option": "Both A and R are true but R is not the correct explanation of A.",
            "explanation": "Detailed explanation of why the correct option is right, referencing the constitutional law principles."
        }}
        """

        return self._generate_json(prompt)

    def _generate_json(self, prompt: str) -> Dict:
        response = self.llm_client.generate_answer(prompt, [], force_json=True)
        try:
            # Clean response if markdown blocks exist
            valid_json = response.replace('```json', '').replace('```', '').strip()
            return json.loads(valid_json)
        except json.JSONDecodeError:
            return {"error": "Failed to generate valid JSON", "raw_response": response}

question_generator = QuestionGeneratorService()
