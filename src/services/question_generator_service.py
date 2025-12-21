
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
        Generates a 'Match List' question by finding (Concept/Case) -> (Definition/Ruling) pairs.
        """
        # Cypher to get 4 random pairs linked by DEFINES or ESTABLISHED
        query = """
        MATCH (s)-[r:DEFINES|ESTABLISHED]->(t)
        WHERE ($file_id IS NULL OR s.file_id = $file_id)
        WITH s, t, r
        ORDER BY rand()
        LIMIT 4
        RETURN s.text as source, t.text as target, type(r) as relation, labels(s) as s_labels
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = graph_service.execute_query(query, params)
        
        if not records or len(records) < 4:
            return {"error": "Not enough graph data to generate a Match List question."}

        pairs = [{"item": r["source"], "match": r["target"]} for r in records]
        
        prompt = f"""
        Role: Legal Exam Setter.
        Task: Create a "Match List" (Match the Following) question.
        
        Data Pairs (Correct Matches):
        {json.dumps(pairs, indent=2)}
        
        Output format (JSON):
        {{
            "question_text": "Match List I with List II...",
            "list_I": ["Item 1", "Item 2", "Item 3", "Item 4"],
            "list_II": ["Definition A", "Definition B", "Definition C", "Definition D"],
            "correct_matches": {{"Item 1": "Definition B", ...}},
            "explanation": "Brief explanation of matches."
        }}
        """
        
        return self._generate_json(prompt)

    def generate_assertion_reason(self, file_id: str = None) -> Dict:
        """
        Generates 'Assertion-Reason' question from Exception/Contradiction relationships.
        """
        # Find logic patterns: HAS_EXCEPTION, CONTRADICTS
        query = """
        MATCH (s)-[r:HAS_EXCEPTION|CONTRADICTS]->(t)
        WHERE ($file_id IS NULL OR s.file_id = $file_id)
        WITH s, t, r
        ORDER BY rand()
        LIMIT 1
        RETURN s.text as main, t.text as exception, type(r) as relation
        """
        params = {"file_id": file_id} if file_id else {"file_id": None}
        records = graph_service.execute_query(query, params)
        
        if not records:
             # Fallback to general reasoning?
             return {"error": "No logic patterns (Exception/Contradiction) found."}
             
        record = records[0]
        
        prompt = f"""
        Role: Legal Exam Setter.
        Task: Create an "Assertion-Reason" question.
        
        Concept: {record['main']}
        Exception/Contradiction: {record['exception']}
        Relation: {record['relation']}
        
        Instructions:
        - Assertion (A): State the concept absolutely or broadly.
        - Reason (R): State the exception or contradiction.
        - Determine the logic option (Both True & Explanation, etc.).
        
        Output format (JSON):
        {{
            "assertion": "...",
            "reason": "...",
            "options": ["Both A and R are true...", ...],
            "correct_option": "...",
            "explanation": "..."
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
