from openai import OpenAI
import google.generativeai as genai
from typing import List, Optional, Any
from config import Config
import logging

logger = logging.getLogger(__name__)

class LlmClient:
    def __init__(self):
        self.provider = Config.llm.PROVIDER

        if self.provider == "openai":
            self.client = OpenAI(api_key=Config.llm.OPENAI_API_KEY)
            self.model = Config.llm.OPENAI_MODEL
            self.max_tokens = Config.llm.OPENAI_MAX_TOKENS
            self.temperature = Config.llm.OPENAI_TEMPERATURE
        elif self.provider == "gemini":
            genai.configure(api_key=Config.llm.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(Config.llm.GEMINI_MODEL)
            self.max_tokens = Config.llm.GEMINI_MAX_TOKENS
            self.temperature = Config.llm.GEMINI_TEMPERATURE


    def generate_answer(self, query: str, context_chunks: List[str], force_json: bool = None) -> str:
        # Context is optional if query is self-contained
        if context_chunks is None:
            context_chunks = []

        should_use_json = force_json if force_json is not None else Config.llm.ENABLE_JSON_RESPONSE

        if should_use_json and self._is_educational_query(query):
            return self._generate_educational_json(query, context_chunks)
        else:
            return self._generate_text_response(query, context_chunks)

    def _is_educational_query(self, query: str) -> bool:
        educational_keywords = [
            "mcq", "questions", "quiz", "test", "exam", "assessment",
            "generate", "create", "multiple choice", "true false",
            "practice", "exercise", "homework", "assignment", "worksheet"
        ]
        return any(keyword in query.lower() for keyword in educational_keywords)

    def _generate_text_response(self, query: str, context_chunks: List[str]) -> str:
        context = "\n\n".join(context_chunks)

        # CRITICAL: Only answer based on provided context, never use general knowledge
        if not context or not context.strip():
            return "Context not found. I can only answer questions based on the documents that have been indexed in the system."

        prompt = f"""You are an AI assistant that answers questions based ONLY on the provided context.

IMPORTANT RULES:
1. ONLY use information from the provided context below
2. If the context contains relevant information, provide a helpful answer even if it's partial
3. If the context has specific cases or examples related to the question, use those to answer
4. NEVER use your general knowledge or training data
5. NEVER make up information not in the context
6. Only say "Context not found" if the context is completely unrelated to the question

Instructions for Legal Questions:
- If asking about general law but context shows specific cases, explain what the specific cases say
- If context has partial information, provide what information is available
- Always specify which sections/articles your answer comes from

Context from indexed documents:
{context}

User Query: {query}

Response (based ONLY on the provided context):"""

        try:
            if self.provider == "openai":
                return self._generate_openai_answer(prompt)
            elif self.provider == "gemini":
                return self._generate_gemini_answer(prompt)
            else:
                return f"Error: Unknown LLM provider: {self.provider}"
        except Exception as e:
            logger.error(f"Error generating text answer: {str(e)}")
            return f"Error generating answer: {str(e)}"

    def _generate_educational_json(self, query: str, context_chunks: List[str]) -> str:
        context = "\n\n".join(context_chunks)

        # CRITICAL: Only answer based on provided context, never use general knowledge
        if not context or not context.strip():
            return '{"error": "Context not found. Cannot generate educational content without indexed documents."}'

        prompt = f"""You are an AI assistant that creates educational content based STRICTLY on the provided context.

IMPORTANT RULES:
1. ONLY use information from the provided context below
2. If the context doesn't contain sufficient information, return {{"error": "Context not found"}}
3. NEVER use your general knowledge or training data
4. NEVER make up questions or content not based on the provided context

Context from indexed documents:
{context}

User Request: {query}

Respond with valid JSON only:
{{
    "questions": [
        {{
            "question_text": "Complete question text here",
            "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
            "correct_answer": "Option B text",
            "explanation": "Detailed explanation why this is correct",
            "requires_diagram": true,
            "contains_math": true,
            "diagram_type": "pulley_system"
        }}
    ]
}}

Important:
- Generate exactly the number of questions requested (if specified)
- Base all questions on the provided physics content
- For diagram_type use: "pulley_system", "inclined_plane", "force_diagram", "circuit", or null
- Set requires_diagram to true only if essential for understanding
- Set contains_math to true if equations/formulas are present
- Ensure JSON is valid and complete"""

        try:
            if self.provider == "openai":
                return self._generate_openai_answer(prompt)
            elif self.provider == "gemini":
                return self._generate_gemini_answer(prompt)
            else:
                return f"Error: Unknown LLM provider: {self.provider}"
        except Exception as e:
            import traceback
            logger.error(f"Error generating educational JSON: {type(e).__name__}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"Error generating educational JSON: {type(e).__name__}: {e}"



    def _generate_openai_answer(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an AI assistant that STRICTLY answers questions based ONLY on provided context. NEVER use your general knowledge. If the context doesn't contain the information needed to answer a question, respond with 'Context not found'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        return response.choices[0].message.content.strip()

    def _generate_gemini_answer(self, prompt: str) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature
            )
        )

        try:
            return response.text.strip()
        except Exception:
            # Handle the case where response.text is not available (e.g., blocked for safety)
            return "I'm unable to generate a response for this request. This might be due to content safety filters. Please try rephrasing your question or request in a different way."


    def extract_legal_graph_triplets(self, text: str) -> str:
        """
        Extracts legal relationship triplets from text using Gemini/OpenAI.
        Returns a JSON string with 'nodes' and 'edges'.
        """
        prompt = f"""
        You are a Legal Knowledge Graph builder. Extract logical relationships from this legal text as structured triplets.
        
        # Schema
        - Nodes: Case, Ruling, Statute, Section, LegalConcept, Condition, Judge, LegalSystem
        - Relations: 
          - (Case)-[:ESTABLISHED]->(LegalConcept/Ruling)
          - (Section)-[:DEFINES]->(LegalConcept)
          - (Section)-[:HAS_EXCEPTION]->(Condition)
          - (Judge)-[:SUPPORTS|CONTRADICTS]->(LegalConcept/Argument)
          - (LegalSystem)-[:ALLOWS|REJECTS]->(LegalConcept)

        # Task
        Analyze the text below. Return a single VALID JSON object with 'nodes' and 'edges'.
        - Nodes have 'id' (unique), 'label', 'text'.
        - Edges have 'source' (id), 'target' (id), 'relation' (uppercase).

        # Text
        {text}
        
        # Output JSON:
        """
        
        # Force JSON mode logic could be enhanced here, but prompt usually suffices with 2.5 Flash
        should_use_json = True 
        
        try:
            if self.provider == "gemini":
                # Ensure we ask for JSON response mime type if possible, or just parse text
                # Ideally pass generation_config={"response_mime_type": "application/json"} if supported
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=4000,
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                return response.text.strip()
            elif self.provider == "openai":
                # OpenAI JSON mode implementation
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a Legal Knowledge Graph builder. Output valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.1,
                    response_format={ "type": "json_object" }
                )
                return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error extracting legal graph triplets: {e}")
            raise