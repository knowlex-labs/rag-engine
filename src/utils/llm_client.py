from openai import OpenAI
import google.generativeai as genai
from typing import List
from config import Config

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
        if not context_chunks:
            return "No relevant context found"

        should_use_json = force_json if force_json is not None else Config.llm.ENABLE_JSON_RESPONSE

        if should_use_json and self._is_educational_query(query):
            return self._generate_educational_json(query, context_chunks)
        else:
            return self._generate_text_response(query, context_chunks)

    def _is_educational_query(self, query: str) -> bool:
        educational_keywords = [
            "mcq", "questions", "quiz", "test", "exam", "assessment",
            "generate", "create questions", "multiple choice", "true false"
        ]
        return any(keyword in query.lower() for keyword in educational_keywords)

    def _generate_text_response(self, query: str, context_chunks: List[str]) -> str:
        context = "\n\n".join(context_chunks)
        prompt = f"""You are an experienced physics teacher with advanced expertise who helps students prepare for examinations. You have deep knowledge of physics concepts and can create educational content including questions, explanations, and practice materials.

Based on the following physics content, respond to the student's request. Whether they ask for explanations, practice questions, MCQs, or any other educational assistance, provide comprehensive and accurate help.

Physics Content:
{context}

Student Request: {query}

Your Response:"""

        try:
            if self.provider == "openai":
                return self._generate_openai_answer(prompt)
            elif self.provider == "gemini":
                return self._generate_gemini_answer(prompt)
        except Exception as e:
            return f"Error generating answer: {str(e)}"

    def _generate_educational_json(self, query: str, context_chunks: List[str]) -> str:
        context = "\n\n".join(context_chunks)
        prompt = f"""You are an experienced physics teacher creating educational content. Generate structured educational material in valid JSON format.

Physics Content:
{context}

Student Request: {query}

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
- Generate exactly the number of questions requested
- For diagram_type use: "pulley_system", "inclined_plane", "force_diagram", "circuit", or null
- Set requires_diagram to true only if essential for understanding
- Set contains_math to true if equations/formulas are present
- Ensure JSON is valid and complete"""

        try:
            if self.provider == "openai":
                return self._generate_openai_answer(prompt)
            elif self.provider == "gemini":
                return self._generate_gemini_answer(prompt)
        except Exception as e:
            return f"Error generating educational JSON: {str(e)}"

    def _generate_openai_answer(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an experienced physics teacher with advanced expertise who helps students prepare for examinations. You have deep knowledge of physics concepts and excel at creating educational content including detailed explanations, practice questions, MCQs, and examination materials. Always provide comprehensive, accurate, and pedagogically sound responses."},
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
        except:
            # Handle the case where response.text is not available (e.g., blocked for safety)
            return "I'm unable to generate a response for this request. This might be due to content safety filters. Please try rephrasing your question or request in a different way."