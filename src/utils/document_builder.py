from typing import List, Dict, Any, Optional
from datetime import datetime
from models.api_models import BookMetadata, ContentType


def build_chunk_document(
    file_id: str,
    file_type: str,
    chunk,
    embedding: List[float],
    book_metadata: Optional[BookMetadata] = None,
    content_type: Optional[ContentType] = None
) -> Dict[str, Any]:
    """
    Build a document for Qdrant storage with chunk and metadata.

    LEGACY METHOD - Used for old hierarchical chunking approach.
    Use build_qdrant_point() for new parser-based approach.

    Args:
        file_id: Unique file identifier
        file_type: Type of file (e.g., 'pdf')
        chunk: HierarchicalChunk object
        embedding: Vector embedding
        book_metadata: Optional book-level metadata
        content_type: Optional content type used for chunking

    Returns:
        Document dictionary for Qdrant
    """
    metadata = {
        "file_type": file_type,
        "chunk_type": chunk.chunk_metadata.chunk_type.value,
        "topic_id": chunk.chunk_metadata.topic_id,
        "chapter_num": chunk.topic_metadata.chapter_num,
        "chapter_title": chunk.topic_metadata.chapter_title,
        "section_num": chunk.topic_metadata.section_num,
        "section_title": chunk.topic_metadata.section_title,
        "page_start": chunk.topic_metadata.page_start,
        "page_end": chunk.topic_metadata.page_end,
        "key_terms": chunk.chunk_metadata.key_terms,
        "equations": chunk.chunk_metadata.equations,
        "has_equations": chunk.chunk_metadata.has_equations,
        "has_diagrams": chunk.chunk_metadata.has_diagrams,
    }

    # Add book-level metadata if provided (for BOOK content type)
    if book_metadata:
        metadata["book_metadata"] = {
            "book_id": book_metadata.book_id,
            "book_title": book_metadata.book_title,
            "book_authors": book_metadata.book_authors,
            "book_edition": book_metadata.book_edition,
            "book_subject": book_metadata.book_subject,
            "total_chapters": book_metadata.total_chapters,
            "total_pages": book_metadata.total_pages
        }

    # Add content type used for chunking (for debugging and filtering)
    if content_type:
        metadata["content_type"] = content_type.value

    return {
        "document_id": file_id,
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "source": file_type,
        "metadata": metadata,
        "vector": embedding
    }


def build_content_document(file_id: str, file_type: str, content: str, embedding: List[float]) -> Dict[str, Any]:
    """
    LEGACY METHOD - Build simple document without hierarchical structure.
    Use build_qdrant_point() for new parser-based approach.
    """
    return {
        "document_id": file_id,
        "text": content,
        "source": file_type,
        "metadata": {
            "file_type": file_type
        },
        "vector": embedding
    }


def build_qdrant_point(
    collection_id: str,
    file_id: str,
    chunk_id: str,
    chunk_text: str,
    embedding: List[float],
    source_type: str,
    file_name: str,
    chunk_type: str = "other",
    hierarchy_level: int = 1,
    parent_chunk_id: Optional[str] = None,
    page_number: Optional[int] = None,
    timestamp: Optional[str] = None,
    topic_tags: Optional[List[str]] = None,
    youtube_channel: Optional[str] = None,
    web_domain: Optional[str] = None,
    extracted_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build Qdrant point with new payload schema for per-user collections.

    Payload Schema:
    - collection_id: Logical folder name (for filtering within user's collection)
    - file_id: Unique file identifier
    - chunk_id: Unique chunk identifier
    - chunk_text: The actual text content
    - chunk_type: 'concept', 'example', 'question', 'other'
    - source_type: 'pdf', 'youtube', 'web'
    - file_name: Original filename/title
    - hierarchy_level: 1=header, 2=section, 3=paragraph
    - parent_chunk_id: Reference to parent chunk (for hierarchical structure)
    - page_number: For PDFs (null for YouTube/web)
    - timestamp: "HH:MM:SS" for YouTube (null for PDF/web)
    - metadata: Rich metadata including Neo4j-ready fields

    Args:
        collection_id: Logical collection/folder name
        file_id: Unique file identifier
        chunk_id: Unique chunk identifier
        chunk_text: Text content of the chunk
        embedding: 1024-dim vector embedding
        source_type: 'pdf', 'youtube', or 'web'
        file_name: Original filename/title
        chunk_type: Classification of chunk
        hierarchy_level: Level in document structure
        parent_chunk_id: Parent chunk for hierarchical structure
        page_number: Page number for PDFs
        timestamp: Timestamp for YouTube videos
        topic_tags: List of topic tags
        youtube_channel: YouTube channel name
        web_domain: Web domain for articles
        extracted_at: ISO timestamp of extraction

    Returns:
        Document dictionary for Qdrant with new schema
    """
    if extracted_at is None:
        extracted_at = datetime.utcnow().isoformat()

    return {
        "document_id": file_id,  # Keep for backward compatibility
        "chunk_id": chunk_id,
        "text": chunk_text,
        "source": source_type,
        "vector": embedding,
        "metadata": {
            # 🔒 MANDATORY FIELD - Logical folder isolation within user
            "collection_id": collection_id,

            # Core Identifiers
            "file_id": file_id,
            "chunk_id": chunk_id,

            # Content
            "chunk_text": chunk_text,

            # Type Information
            "chunk_type": chunk_type,
            "source_type": source_type,
            "file_name": file_name,

            # Location Information
            "page_number": page_number,
            "timestamp": timestamp,

            # Hierarchy (for Neo4j future integration)
            "hierarchy_level": hierarchy_level,
            "parent_chunk_id": parent_chunk_id,

            # Rich Metadata (Neo4j-ready)
            "topic_tags": topic_tags or [],
            "entities": [],  # PLACEHOLDER for Neo4j
            "concepts": [],  # PLACEHOLDER for Neo4j
            "extracted_at": extracted_at,
            "youtube_channel": youtube_channel,
            "web_domain": web_domain,
        }
    }