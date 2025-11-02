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

    def generate_answer(self, query: str, context_chunks: List[str]) -> str:
        if not context_chunks:
            return "No relevant context found"

        context = "\n\n".join(context_chunks)
        prompt = f"""Based on the following context, answer the user's question. If the context doesn't contain enough information to answer the question, say so clearly.

Context:
{context}

Question: {query}

Answer:"""

        try:
            if self.provider == "openai":
                return self._generate_openai_answer(prompt)
            elif self.provider == "gemini":
                return self._generate_gemini_answer(prompt)
        except Exception as e:
            return f"Error generating answer: {str(e)}"

    def _generate_openai_answer(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based only on the provided context. Be accurate and concise."},
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
            return "I'm unable to generate a response for this query. Please try rephrasing your question."