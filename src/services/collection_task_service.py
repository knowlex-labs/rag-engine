import logging
import time
from typing import List, Dict, Any, Optional
from services.query_service import QueryService
from services.enhanced_question_generator import enhanced_question_generator
from utils.llm_client import LlmClient
from models.question_models import DifficultyLevel, QuestionGenerationResponse

logger = logging.getLogger(__name__)

class CollectionTaskService:
    """Service for collection-specific tasks like specialized chat, quiz, and summary."""
    
    def __init__(self):
        self.query_service = QueryService()
        self.llm_client = LlmClient()
        self.question_generator = enhanced_question_generator

    async def generate_summary(self, collection_id: str, user_id: str) -> Dict[str, Any]:
        """Generate a professional, high-quality, student-friendly summary of a collection."""
        start_time = time.time()
        
        # 1. Retrieve key content from collection
        # We search for general overview content
        logger.info(f"Generating summary for collection: {collection_id}")
        chunks = await self.query_service.retrieve_context(
            query="comprehensive overview of everything in this collection",
            user_id=user_id,
            collection_ids=[collection_id],
            top_k=15
        )
        
        # Fallback: If semantic search for "overview" fails, just get the top chunks by ID
        if not chunks:
            logger.info(f"Semantic overview search failed for {collection_id}, falling back to direct retrieval")
            try:
                # Direct query to get any chunks from this collection
                fallback_query = """
                MATCH (c:Chunk)
                WHERE c.collection_id = $collection_id
                RETURN c.text as text
                LIMIT 15
                """
                fallback_results = self.query_service.neo4j_repo.graph_service.execute_query(
                    fallback_query, {"collection_id": collection_id}
                )
                chunks = [{"text": r["text"]} for r in fallback_results]
            except Exception as e:
                logger.error(f"Fallback retrieval failed: {e}")

        if not chunks:
            logger.warning(f"No content found in collection {collection_id} even after fallback")
            return {"summary": "No content found in this collection to summarize.", "processing_time_ms": 0}

        context_texts = [c['text'] for c in chunks]
        context = "\n\n".join(context_texts)

        prompt = f"""You are a professional educational content creator and expert tutor.
Your goal is to provide a high-quality, comprehensive, and student-friendly summary of the following document contents.

### GUIDELINES:
1. **Be Professional & Structured**: Use clear headings, bullet points, and sections.
2. **Student-Friendly**: Use an encouraging, instructional tone. Explain complex terms simply and use analogies if helpful.
3. **High Quality**: Don't just list facts. Provide a narrative summary that shows how concepts connect. Focus on the 'Why' and 'How' not just the 'What'.
4. **Formatting**: Use markdown (bolding, lists, tables if appropriate) to make it highly readable.
5. **Educational Excellence**: Ensure the language is clear, engaging, and facilitates easy learning.

### DOCUMENT CONTEXT:
{context}

### YOUR TASK:
Provide a detailed summary of the above content. Start with an 'Overview' section, followed by 'Key Concepts', 'Detailed Breakdown' (with sub-points), and 'Conclusion'.
If this is legal content, cite sections/articles where possible.

### RESPONSE:"""

        summary = self.llm_client.generate_answer(prompt, context_texts)
        
        return {
            "summary": summary,
            "collection_id": collection_id,
            "chunks_analyzed": len(chunks),
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }

    async def generate_quiz(self, collection_id: str, num_questions: int = 10, difficulty: str = "moderate") -> QuestionGenerationResponse:
        """Generate a mixed quiz (MCQ, AR, Match) from a collection."""
        diff_enum = DifficultyLevel.MODERATE
        if difficulty.lower() == "easy":
            diff_enum = DifficultyLevel.EASY
        elif difficulty.lower() == "difficult" or difficulty.lower() == "hard":
            diff_enum = DifficultyLevel.DIFFICULT
            
        return await self.question_generator.generate_mixed_quiz(collection_id, count=num_questions, difficulty=diff_enum)

collection_task_service = CollectionTaskService()
