from typing import List, Dict, Any


def build_chunk_document(file_id: str, file_type: str, chunk, embedding: List[float]) -> Dict[str, Any]:
    return {
        "document_id": file_id,
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "source": file_type,
        "metadata": {
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
        },
        "vector": embedding
    }


def build_content_document(file_id: str, file_type: str, content: str, embedding: List[float]) -> Dict[str, Any]:
    return {
        "document_id": file_id,
        "text": content,
        "source": file_type,
        "metadata": {
            "file_type": file_type
        },
        "vector": embedding
    }