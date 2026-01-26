"""
Raw Data API Routes
Pure data retrieval endpoints - no AI/LLM processing.
Returns embeddings, chunks, and raw data for backend processing.
"""

import logging
import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from utils.embedding_client import EmbeddingClient
from repositories.neo4j_repository import Neo4jRepository
from config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class EmbeddingsRequest(BaseModel):
    """Request for generating embeddings from texts."""
    texts: List[str] = Field(..., description="List of texts to embed", min_items=1, max_items=100)

class EmbeddingsResponse(BaseModel):
    """Response with generated embeddings."""
    embeddings: List[List[float]] = Field(..., description="List of embedding vectors")
    model: str = Field(..., description="Embedding model used")
    dimensions: int = Field(..., description="Vector dimensions")
    count: int = Field(..., description="Number of embeddings generated")

class ChunksRequest(BaseModel):
    """Request for retrieving chunks via vector similarity search."""
    query: str = Field(..., description="Query text for similarity search")
    collection_ids: Optional[List[str]] = Field(None, description="Collection IDs to search in")
    limit: int = Field(10, description="Maximum chunks to return", ge=1, le=50)

class ChunkData(BaseModel):
    """Single chunk with metadata."""
    chunk_id: str
    text: str
    score: float
    collection_id: Optional[str] = None
    section_title: Optional[str] = None
    article_number: Optional[str] = None
    metadata: Optional[dict] = None

class ChunksResponse(BaseModel):
    """Response with raw chunks from vector search."""
    chunks: List[ChunkData] = Field(..., description="Retrieved chunks with scores")
    query: str = Field(..., description="Original query")
    total: int = Field(..., description="Total chunks returned")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


# =============================================================================
# EMBEDDINGS ENDPOINT
# =============================================================================

@router.post("/embeddings", response_model=EmbeddingsResponse)
async def generate_embeddings(
    request: EmbeddingsRequest,
    x_user_id: str = Header(..., description="User ID for logging")
) -> EmbeddingsResponse:
    """
    Generate embeddings for provided texts.
    
    Returns raw embedding vectors for use in similarity search or other processing.
    Uses the configured embedding provider (Gemini, OpenAI, or HuggingFace).
    
    **Example:**
    ```json
    {
        "texts": ["Article 21 of the constitution", "Right to life"]
    }
    ```
    """
    try:
        start_time = time.time()
        
        logger.info(f"📥 Embeddings request from user: {x_user_id}")
        logger.info(f"   Texts count: {len(request.texts)}")
        logger.info(f"   First text preview: {request.texts[0][:100]}..." if request.texts else "   No texts")
        
        if not request.texts:
            raise HTTPException(status_code=400, detail="At least one text is required")
        
        # Generate embeddings
        logger.info(f"🔄 Generating embeddings using provider: {Config.embedding.PROVIDER}")
        embedding_client = EmbeddingClient()
        embeddings = embedding_client.generate_embeddings(request.texts)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        model_name = EmbeddingClient._model_name if hasattr(EmbeddingClient, '_model_name') else Config.embedding.MODEL_NAME
        dimensions = len(embeddings[0]) if embeddings else 0
        
        logger.info(f"✅ Generated {len(embeddings)} embeddings in {processing_time}ms")
        logger.info(f"   Model: {Config.embedding.PROVIDER}/{model_name}")
        logger.info(f"   Dimensions: {dimensions}")
        
        return EmbeddingsResponse(
            embeddings=embeddings,
            model=f"{Config.embedding.PROVIDER}/{model_name}",
            dimensions=dimensions,
            count=len(embeddings)
        )
        
    except Exception as e:
        logger.error(f"❌ Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")


# =============================================================================
# CHUNKS ENDPOINT
# =============================================================================

@router.post("/chunks", response_model=ChunksResponse)
async def retrieve_chunks(
    request: ChunksRequest,
    x_user_id: str = Header(..., description="User ID for logging")
) -> ChunksResponse:
    """
    Retrieve raw chunks via vector similarity search.
    
    Returns chunks with relevance scores - no AI processing or answer generation.
    Backend should use these chunks to generate answers with its own LLM.
    
    **Collection IDs:**
    - `constitution-golden-source`: Constitution of India
    - `bns-golden-source`: Bharatiya Nyaya Sanhita
    - `bare-acts-golden-source`: Other Bare Acts
    
    **Example:**
    ```json
    {
        "query": "What is Article 21?",
        "collection_ids": ["constitution-golden-source"],
        "limit": 10
    }
    ```
    """
    try:
        start_time = time.time()
        
        logger.info(f"📥 Chunks request from user: {x_user_id}")
        logger.info(f"   Query: {request.query[:100]}..." if len(request.query) > 100 else f"   Query: {request.query}")
        logger.info(f"   Collections: {request.collection_ids or 'ALL'}")
        logger.info(f"   Limit: {request.limit}")
        
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Generate query embedding
        logger.info(f"🔄 Generating query embedding...")
        embedding_client = EmbeddingClient()
        query_embedding = embedding_client.generate_single_embedding(request.query)
        logger.info(f"   Embedding generated: {len(query_embedding)} dimensions")
        
        # Determine collection filter
        collection_ids = request.collection_ids
        if not collection_ids:
            # Default to all legal collections
            collection_ids = [
                'constitution-golden-source',
                'bns-golden-source',
                'bare-acts-golden-source'
            ]
        
        # Execute vector search via Neo4j
        logger.info(f"🔍 Searching Neo4j vector index...")
        neo4j_repo = Neo4jRepository()
        
        cypher = """
        CALL db.index.vector.queryNodes('legal_chunks_index', $limit, $query_embedding)
        YIELD node as c, score
        WHERE c.collection_id IN $collection_ids
        RETURN 
            c.chunk_id as chunk_id,
            c.text as text,
            score,
            c.collection_id as collection_id,
            c.section_title as section_title,
            c.chapter_title as chapter_title,
            c.file_id as file_id,
            c.chunk_type as chunk_type,
            c.key_terms as key_terms
        ORDER BY score DESC
        LIMIT $limit
        """
        
        records = neo4j_repo.graph_service.execute_query(cypher, {
            'query_embedding': query_embedding,
            'collection_ids': collection_ids,
            'limit': request.limit
        })
        
        # Transform to response format
        chunks = []
        for record in records:
            chunk_id = record.get('chunk_id', '')
            
            # Extract article/section number from chunk_id
            # Format: constitution-art-24-chunk-001 or bns-sec-302-chunk-001
            article_number = None
            if '-art-' in chunk_id:
                # Constitution: extract article number
                parts = chunk_id.split('-art-')
                if len(parts) > 1:
                    article_number = parts[1].split('-chunk-')[0]
            elif '-sec-' in chunk_id:
                # BNS/Acts: extract section number
                parts = chunk_id.split('-sec-')
                if len(parts) > 1:
                    article_number = parts[1].split('-chunk-')[0]
            
            chunks.append(ChunkData(
                chunk_id=chunk_id,
                text=record.get('text', ''),
                score=float(record.get('score', 0.0)),
                collection_id=record.get('collection_id'),
                section_title=record.get('section_title'),
                article_number=article_number,  # Extracted from chunk_id
                metadata={
                    'chapter_title': record.get('chapter_title'),
                    'file_id': record.get('file_id'),
                    'chunk_type': record.get('chunk_type'),
                    'key_terms': record.get('key_terms', [])
                }
            ))
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(f"✅ Retrieved {len(chunks)} chunks in {processing_time}ms")
        if chunks:
            logger.info(f"   Top chunk score: {chunks[0].score:.4f}")
            logger.info(f"   Top chunk article: {chunks[0].article_number or 'N/A'}")
            logger.info(f"   Top chunk preview: {chunks[0].text[:150]}...")
            logger.info(f"   Section: {chunks[0].section_title or 'N/A'}")
        
        return ChunksResponse(
            chunks=chunks,
            query=request.query,
            total=len(chunks),
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"❌ Chunk retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chunk retrieval failed: {str(e)}")
