#!/usr/bin/env python3
"""
Test script for hierarchical chunking implementation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.hierarchical_chunking_service import HierarchicalChunkingService
from models.api_models import ChunkType
import json

def test_hierarchical_chunking():
    """Test the hierarchical chunking service."""

    print("=" * 80)
    print("Testing Hierarchical Chunking Service")
    print("=" * 80)

    # Initialize service
    service = HierarchicalChunkingService()

    # Test PDF path
    pdf_path = "/home/user/rag-engine/tests/fixtures/resnick-halliday-Force-and-motion-1.pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found at: {pdf_path}")
        return False

    print(f"\n📄 Processing PDF: {pdf_path}")

    try:
        # Process the PDF
        chunks = service.chunk_pdf_hierarchically(
            file_path=pdf_path,
            document_id="test-doc-001",
            chunk_size=512,
            chunk_overlap=50
        )

        print(f"\n✅ Successfully generated {len(chunks)} chunks")

        # Analyze chunk distribution
        chunk_type_counts = {}
        topics = {}

        for chunk in chunks:
            # Count chunk types
            chunk_type = chunk.chunk_metadata.chunk_type
            chunk_type_counts[chunk_type] = chunk_type_counts.get(chunk_type, 0) + 1

            # Track topics
            topic_key = f"{chunk.topic_metadata.chapter_num}.{chunk.topic_metadata.section_num}"
            if topic_key not in topics:
                topics[topic_key] = {
                    'chapter_title': chunk.topic_metadata.chapter_title,
                    'section_title': chunk.topic_metadata.section_title,
                    'chunk_count': 0
                }
            topics[topic_key]['chunk_count'] += 1

        # Print statistics
        print("\n" + "=" * 80)
        print("📊 CHUNK TYPE DISTRIBUTION")
        print("=" * 80)
        for chunk_type, count in chunk_type_counts.items():
            percentage = (count / len(chunks)) * 100
            print(f"  {chunk_type.name:12} : {count:3} chunks ({percentage:5.1f}%)")

        print("\n" + "=" * 80)
        print("📚 TOPIC HIERARCHY")
        print("=" * 80)
        for topic_key, info in sorted(topics.items()):
            if info['chapter_title']:
                print(f"\n  Topic {topic_key}: {info['chapter_title']}")
                if info['section_title']:
                    print(f"    Section: {info['section_title']}")
                print(f"    Chunks: {info['chunk_count']}")

        # Show sample chunks
        print("\n" + "=" * 80)
        print("📝 SAMPLE CHUNKS (First 3)")
        print("=" * 80)

        for i, chunk in enumerate(chunks[:3]):
            print(f"\n--- Chunk {i+1} ---")
            print(f"  Type: {chunk.chunk_metadata.chunk_type.name}")
            print(f"  Chapter: {chunk.topic_metadata.chapter_title or 'N/A'}")
            print(f"  Section: {chunk.topic_metadata.section_title or 'N/A'}")
            print(f"  Page: {chunk.topic_metadata.page_start}")
            print(f"  Has Equations: {chunk.chunk_metadata.has_equations}")
            print(f"  Has Diagrams: {chunk.chunk_metadata.has_diagrams}")
            if chunk.chunk_metadata.key_terms:
                print(f"  Key Terms: {', '.join(chunk.chunk_metadata.key_terms[:3])}")
            if chunk.chunk_metadata.equations:
                print(f"  Equations: {chunk.chunk_metadata.equations[:2]}")
            print(f"  Text Preview: {chunk.text[:150]}...")

        # Test query intent detection (from QueryService)
        print("\n" + "=" * 80)
        print("🔍 QUERY INTENT DETECTION")
        print("=" * 80)

        from services.query_service import QueryService
        query_service = QueryService()

        test_queries = [
            "What is Newton's second law?",
            "Show me an example of force calculation",
            "How do I solve momentum problems?",
            "Explain the concept of force and motion"
        ]

        for query in test_queries:
            intent = query_service._detect_query_intent(query)
            print(f"  Query: '{query}'")
            print(f"  Detected Intent: {intent or 'General (mixed search)'}\n")

        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_hierarchical_chunking()
    sys.exit(0 if success else 1)
